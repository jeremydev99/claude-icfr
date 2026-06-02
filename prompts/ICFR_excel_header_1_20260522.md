# ICFR_excel_header_1_20260522.md — Excel 헤더 자동 인식 (시트명 무관)

## 메타

| 항목 | 값 |
|---|---|
| 작업 유형 | 백엔드 수정 (POST /api/rcm/upload-excel) |
| 담당 | TrustBuilder |
| 제안자 | Regina (FE 작업 중 발견) |
| 결정 출처 | claude.ai 사전 승인 |
| 예상 시간 | 1~1.5시간 |
| 커밋 메시지 제안 | `feat(backend): Excel 헤더 자동 인식 (시트명 무관, 동의어 사전, 단계적 확장)` |

---

## 0. 작업 시작

```powershell
cd C:\claudeprojects\ICFR
```

`backend/app/api/rcm.py` 의 `upload-excel` 엔드포인트 + 파싱 로직 수정.

---

## 1. 본질

**현재**: 시트명 "RCM" 필수 + 헤더 행 8행 고정.

**변경 후**: 시트명 무관 + 헤더 동의어 사전 + 헤더 행 자동 탐색 (단계적 확장).

> 💡 사업 가치: 사이냅소프트 외 다른 회사 양식 (회계법인별·업종별) 자동 호환. AI 자동 ICFR 설정 비전의 기반 기술.

---

## 2. 동의어 사전 (필수 헤더 3개)

`backend/app/services/excel_parser.py` (신규 또는 기존 파일에 추가):

```python
HEADER_SYNONYMS = {
    "process_code": [
        "프로세스번호", "프로세스 번호",
        "프로세스ID", "프로세스 ID",
        "프로세스코드", "프로세스 코드",
        "Process No", "Process Number",
        "Process ID", "Process Code",
    ],
    "control_code": [
        "통제활동번호", "통제활동 번호",
        "통제번호", "통제 번호",
        "통제코드", "통제 코드",
        "통제ID", "통제 ID",
        "통제활동코드", "통제활동 코드",
        "Control No", "Control Number",
        "Control ID", "Control Code",
        "Control Activity ID",
    ],
    "control_name": [
        "통제활동이름", "통제활동 이름",
        "통제활동명", "통제활동 명",
        "통제이름", "통제 이름",
        "통제명",
        "Control Name",
        "Control Activity Name",
        "Control Activity",
    ],
}
```

> ⚠️ ADR-0020 준수: 사전은 **하드코딩 dict**. DB·설정 파일 등록 금지. 추가 추상화 금지.

---

## 3. 핵심 함수 (단순 함수만)

### 3.1 정규화 함수

```python
def _normalize(s: str) -> str:
    """공백 제거 + 소문자."""
    if not s:
        return ""
    return s.replace(" ", "").replace("\u00a0", "").lower()
```

### 3.2 행에서 헤더 매칭 확인

```python
def _row_matches_headers(row, synonyms_dict) -> dict[str, int] | None:
    """한 행에서 필수 헤더 위치 매핑 발견 시 {key: col_idx} 반환, 아니면 None.
    
    모든 필수 헤더 (synonyms_dict의 키) 가 매칭되어야 성공.
    """
    normalized_syns = {
        key: [_normalize(s) for s in syns]
        for key, syns in synonyms_dict.items()
    }
    
    mapping = {}
    for col_idx, cell in enumerate(row):
        if cell is None:
            continue
        cell_norm = _normalize(str(cell))
        for key, norm_syns in normalized_syns.items():
            if key in mapping:
                continue
            if cell_norm in norm_syns:
                mapping[key] = col_idx
                break
    
    # 모든 필수 키 매칭됐는지
    if len(mapping) == len(synonyms_dict):
        return mapping
    return None
```

### 3.3 시트에서 헤더 행 탐색

```python
def _find_header_row(ws, max_row: int) -> tuple[int, dict[str, int]] | None:
    """시트의 1~max_row 안에서 헤더 행 탐색.
    
    Returns: (header_row_idx, column_mapping) or None
    """
    for row_idx, row in enumerate(
        ws.iter_rows(min_row=1, max_row=max_row, values_only=True),
        start=1,
    ):
        mapping = _row_matches_headers(row, HEADER_SYNONYMS)
        if mapping is not None:
            return row_idx, mapping
    return None
```

### 3.4 워크북에서 RCM 시트 탐색

```python
def find_rcm_sheet(wb, max_row: int = 15) -> tuple[str, int, dict[str, int]] | None:
    """모든 시트 순회 → 헤더 매칭 시 (sheet_name, header_row, mapping) 반환.
    
    찾으면 첫 번째 매칭 시트 반환. None 이면 사용자에게 확장 요청 필요.
    """
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        result = _find_header_row(ws, max_row)
        if result is not None:
            header_row, mapping = result
            return sheet_name, header_row, mapping
    return None
```

> ⚠️ ADR-0020 준수: ExcelParser·HeaderDetector 클래스 만들지 말 것. 함수만.

---

## 4. API 엔드포인트 수정

`backend/app/api/rcm.py`:

### 4.1 query parameter 추가

```python
@router.post("/upload-excel")
def upload_excel(
    file: UploadFile,
    mode: str = "preview",  # "preview" or "commit"
    expand_to: int = 15,    # 헤더 탐색 최대 행 (기본 15)
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    1차: expand_to=15 (자동)
    2차: expand_to=30 (사용자 승인 시 클라이언트가 재호출)
    3차: expand_to=130 (사용자 승인 시)
    """
    contents = file.file.read()
    wb = load_workbook(BytesIO(contents), read_only=True, data_only=True)
    
    found = find_rcm_sheet(wb, max_row=expand_to)
    
    if found is None:
        # 헤더 못 찾음 — 단계별 응답
        return _build_not_found_response(wb, expand_to)
    
    sheet_name, header_row, mapping = found
    ws = wb[sheet_name]
    
    # 기존 파싱 로직 (헤더 행 + 컬럼 매핑 사용)
    # ...
```

### 4.2 못 찾았을 때 응답

```python
def _build_not_found_response(wb, current_range: int):
    """단계적 확장 또는 최종 오류 응답."""
    
    NEXT_STAGE = {15: 30, 30: 130}
    
    if current_range in NEXT_STAGE:
        next_range = NEXT_STAGE[current_range]
        return JSONResponse(
            status_code=200,  # 정상 흐름의 일부
            content={
                "status": "needs_expansion",
                "message": (
                    f"1~{current_range}행에서 RCM 헤더를 찾지 못했습니다. "
                    f"{current_range+1}~{next_range}행까지 확장 검색할까요?"
                ),
                "current_range": current_range,
                "next_range": next_range,
                "expand_param": f"?expand_to={next_range}",
                "sheets_checked": wb.sheetnames,
            },
        )
    
    # 최종 실패 (130행까지 시도)
    return JSONResponse(
        status_code=422,
        content={
            "status": "header_not_found",
            "error": "RCM 헤더가 있는 시트를 찾을 수 없습니다.",
            "checked_sheets": wb.sheetnames,
            "checked_rows": "1~130",
            "required_headers": {
                "process_code": "프로세스번호 / 프로세스ID / Process ID / Process No 등",
                "control_code": "통제활동번호 / 통제번호 / Control ID / Control No 등",
                "control_name": "통제활동이름 / 통제명 / Control Name 등",
            },
            "suggestion": (
                "헤더가 다른 이름이거나 130행 이후에 있다면 관리자에게 문의. "
                "동의어 사전 확장이 필요합니다."
            ),
        },
    )
```

---

## 5. 기존 파싱 로직 호환

기존 코드:
```python
# B = 1, C = 2, D = 3, ... (고정)
p_code = str(row[1])
c_code = str(row[6])
```

수정 후:
```python
# mapping 사용
p_code = str(row[mapping["process_code"]])
c_code = str(row[mapping["control_code"]])
c_name = str(row[mapping["control_name"]])

# 나머지 컬럼 (H, I, O, P, Q, R 등) 도 사이냅소프트 양식 기준 상대 위치로
# (현재 코드 그대로 유지, mapping 은 필수 3개만)
```

> 💡 **사이냅소프트 양식 호환 보장**: 다른 컬럼들 (담당자·위험내용·통제목적 등) 은 사이냅소프트 기준 상대 위치 유지. 본 작업은 **시트 인식 + 헤더 위치 자동 탐색만**.

---

## 6. 데이터 시작 행

기존: `min_row=8` 고정.

수정: `min_row=header_row + 1` (탐색된 헤더 행의 다음부터).

```python
for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
    if row[mapping["process_code"]] is None:
        break  # 데이터 끝
    # ... 파싱 ...
```

---

## 7. pytest 추가

`backend/tests/test_rcm.py`:

```python
def test_upload_excel_sheet_name_arbitrary():
    """시트명이 'RCM' 이 아니어도 헤더 매칭 시 인식."""
    # 시트명 "통제매트릭스" 인 Excel 생성·업로드
    # → 200 OK + valid_rows 반환

def test_upload_excel_header_row_position_varies():
    """헤더가 8행이 아닌 5행에 있어도 인식."""

def test_upload_excel_korean_synonyms():
    """헤더 이름이 동의어 (예: '통제코드' 대신 '통제번호') 인 경우 인식."""

def test_upload_excel_english_synonyms():
    """헤더가 영문 (Control ID 등) 인 경우 인식."""

def test_upload_excel_normalization():
    """공백·대소문자 차이 ('Process  ID' vs 'process id') 인식."""

def test_upload_excel_no_match_returns_expansion():
    """헤더 못 찾으면 needs_expansion 응답 (1차 시도)."""

def test_upload_excel_no_match_after_130_returns_error():
    """130 까지 시도해도 못 찾으면 422 + 가이드."""

def test_upload_excel_sub_process_skipped():
    """sub_process_code, risk_code 컬럼 없어도 (Q1 결정: 3개만 필수) 다른 정보로 처리."""
```

→ 기존 52개 + 신규 ~7개 = **59개**.

---

## 8. 검증 시나리오 (수동)

작업 완료 후 사용자가 수동 검증:

| 시나리오 | 기대 |
|---|---|
| 사이냅소프트 양식 그대로 (시트명 RCM) | 200 + valid_rows: 93 (기존과 동일) |
| 시트명 "통제매트릭스" 변경 후 업로드 | 200 + 정상 인식 ✅ |
| 1~7행에 메모, 8행 헤더 | 200 + 정상 (1차 15행 안) |
| 헤더가 20행에 있는 양식 | needs_expansion 응답 → 30 확장 시도 시 정상 |
| 헤더 없는 빈 시트 | 422 + 동의어 가이드 |

---

## 9. ClaudeICFR.md 갱신

### 9.1 섹션 6 (ADR) — 별도 ADR 등록 안 함

본 변경은 **버그 수정 + 강건성 강화** 라 ADR 등록 안 함. 단, 다음 ADR-0024 (가칭, 미래) 의 기반:
- "Excel 양식 헤더 동의어 사전 확장 정책"

### 9.2 섹션 14 (변경 로그) 최상단

```markdown
- **2026-05-22 / TrustBuilder + Claude** — Excel 헤더 자동 인식 (Regina 제안). 시트명 무관, 동의어 사전 (한/영), 헤더 행 자동 탐색 (1~15→30→130 단계 확장). 사이냅소프트 양식 호환 유지 + 다양한 회사 양식 호환. pytest ~7개 추가.
```

### 9.3 섹션 18 (일일 로그)

```markdown
- **TrustBuilder**: Excel 헤더 자동 인식 (Regina 제안 받음). 시트명·헤더 위치·헤더명 모두 유연. AI 자동 ICFR 설정 비전의 기반 기술 첫 단계.
```

---

## 10. 진행 단계

| Step | 시간 |
|---|---|
| 1. excel_parser.py 함수 4개 추가 | 30분 |
| 2. upload-excel 엔드포인트 수정 | 20분 |
| 3. pytest 7개 추가 | 30분 |
| 4. 사이냅소프트 양식 그대로 회귀 테스트 | 10분 |
| 5. ClaudeICFR.md 갱신 | 10분 |
| **합계** | **약 1.5시간** |

---

## 11. 검증 체크리스트

- [ ] 사이냅소프트 양식 (시트명 RCM, 헤더 7행) 그대로 업로드 시 93통제 인식 ✅
- [ ] 시트명을 다른 이름으로 바꾼 사본 업로드 시 인식 ✅
- [ ] 헤더 위치를 5행으로 변경한 사본 업로드 시 인식 ✅
- [ ] 헤더명을 영문으로 바꾼 사본 업로드 시 인식 ✅
- [ ] 헤더 못 찾는 양식 업로드 시 needs_expansion 응답 ✅
- [ ] expand_to=30 재호출 시 인식 ✅
- [ ] 130까지 시도 후 못 찾으면 422 + 가이드 ✅
- [ ] pytest ~59개 전부 통과
- [ ] **ADR-0020 준수**: 클래스·서비스 추상화 0개

---

## 12. 사용자 원칙 강조

> ⚠️ **절대 만들지 말 것**:
> - ❌ `ExcelParser` 클래스
> - ❌ `HeaderDetector` 클래스
> - ❌ `RCMHeaderMatcher` 추상화
> - ❌ Strategy 패턴 (다양한 양식 매칭 전략)
> - ❌ 동의어 사전을 DB 또는 설정 파일에 저장 (현재 단계에선 하드코딩)
>
> **함수 4개만 추가** (_normalize, _row_matches_headers, _find_header_row, find_rcm_sheet) + API 엔드포인트 수정.

---

## 13. 사용자 OK 후 push

```bash
git add -A
git commit -m "feat(backend): Excel 헤더 자동 인식 (시트명 무관, 동의어 사전, 단계적 확장)"
git push origin main
```

---

## 14. 완료 시 결과 요약 요구

| 항목 | 결과 |
|---|---|
| 신규 함수 | 4개 (_normalize, _row_matches_headers, _find_header_row, find_rcm_sheet) |
| API 수정 | upload-excel 에 expand_to 파라미터 추가 |
| 동의어 사전 | HEADER_SYNONYMS dict (3 키 × 8~12 동의어) |
| 단계 확장 | 15 → 30 → 130 |
| pytest | 기존 52 + 신규 7 = 59 (모두 통과) |
| 사이냅소프트 양식 회귀 | ✅ 93통제 그대로 인식 |
| 추상화 | 0개 (ADR-0020 준수) |

OK 주시면 push.
