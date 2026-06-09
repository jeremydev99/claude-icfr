# ICFR_search_enrichment_1_20260602.md — search 엔드포인트 응답 확장 (ControlSearchOut)

## 메타

| 항목 | 값 |
|---|---|
| 작업 유형 | 백엔드 — 스키마 신규 + 쿼리 JOIN 확장 |
| 담당 | TrustBuilder |
| 제안자 | Regina (FE useControls 실 API 연결 작업 중) |
| 예상 시간 | 30분~1시간 |
| 영향 파일 | `backend/app/schemas/rcm.py`, `backend/app/api/rcm.py`, `backend/tests/test_rcm.py` |
| 커밋 메시지 | `feat(backend): ControlSearchOut 스키마 추가 — search 응답에 process/sub_process/risk_level/assertions 포함` |

---

## 0. 작업 시작

```powershell
cd C:\claudeprojects\ICFR
```

`backend/app/schemas/rcm.py`, `backend/app/api/rcm.py` 수정.

---

## 1. 본질

**현재**: `GET /api/rcm/controls/search` 응답에 Control 자체 필드만. 관계 데이터 (Risk→SubProcess→Process, ControlAssertion) 미포함.

**변경**: 새 스키마 `ControlSearchOut` 도입. 4개 신규 필드 (process_code, sub_process_code, risk_level, assertions) 포함.

**효과**: Regina 의 useControls hook 이 한 번의 API 호출로 통제 목록 + 관계 정보 받음. FE 화면이 매 행마다 별도 API 호출 안 함.

---

## 2. 사용자 사전 승인

| Q | 결정 |
|---|---|
| Q1. 스키마 분리 | **새 스키마 ControlSearchOut 도입** (기존 ControlOut 보존) |
| Q2. 확장 범위 | **search 엔드포인트만 적용** |
| Q3. 쿼리 방식 | **JOIN 으로 한 쿼리** (N+1 회피) |

---

## 3. 스키마 변경

`backend/app/schemas/rcm.py` 끝부분에 추가:

```python
class ControlSearchOut(ControlOut):
    """Search 엔드포인트 전용 응답 스키마.
    
    기존 ControlOut + 관계 데이터 (process_code, sub_process_code, 
    risk_level, assertions).
    
    FE 목록 화면이 별도 API 호출 없이 모든 정보를 받도록.
    """
    process_code: str | None = None
    sub_process_code: str | None = None
    risk_level: str | None = None  # risk.assessment_level
    assertions: list[str] = []     # ["E", "C", "V"] 형태
```

> ⚠️ ADR-0020 준수: 새 클래스·서비스 추상화 금지. **Pydantic 스키마만 1개 추가**.

---

## 4. search 엔드포인트 수정

`backend/app/api/rcm.py` 의 `search_controls` 함수:

### 4.1 응답 모델 변경

```python
@router.get("/controls/search", response_model=ControlSearchResponse)
def search_controls(
    # ... 기존 파라미터들 ...
):
    """기존 로직 유지, 응답 매핑만 확장."""
```

여기서 `ControlSearchResponse` 는:

```python
class ControlSearchResponse(BaseModel):
    items: list[ControlSearchOut]  # ← 신규 스키마 사용
    total: int
    skip: int
    limit: int
    sort: str
```

### 4.2 쿼리 JOIN 확장

기존:
```python
query = db.query(Control)
```

변경:
```python
query = (
    db.query(Control)
    .options(
        joinedload(Control.risk)
            .joinedload(Risk.sub_process)
            .joinedload(SubProcess.process),
        joinedload(Control.assertions),
    )
)
```

> 💡 SQLAlchemy 의 `joinedload` 가 N+1 자동 회피. 한 SQL 로 모든 관계 조회.

### 4.3 응답 매핑

```python
items_out = []
for c in items:
    out = ControlSearchOut.model_validate(c)
    # 관계 데이터 매핑
    if c.risk:
        out.risk_level = c.risk.assessment_level
        if c.risk.sub_process:
            out.sub_process_code = c.risk.sub_process.code
            if c.risk.sub_process.process:
                out.process_code = c.risk.sub_process.process.code
    # assertions: ControlAssertion → assertion_code 만 추출
    out.assertions = [a.assertion_code for a in c.assertions]
    items_out.append(out)

return {
    "items": items_out,
    "total": total,
    ...
}
```

> ⚠️ ADR-0020 준수: 별도 매핑 함수 추출 금지. 명시적 if 분기.

---

## 5. 회귀 보호

기존 `ControlOut` 스키마 그대로 유지 → 다른 엔드포인트 (`GET /controls`, `GET /controls/{id}` 등) 응답 형식 변경 없음. FE 의 다른 화면 안전.

---

## 6. pytest 추가

`backend/tests/test_rcm.py`:

```python
def test_search_response_includes_process_code():
    """search 응답에 process_code 포함."""
    # 사이냅소프트 통제 1개 선택 → response items[0].process_code 가 "EL" 등

def test_search_response_includes_sub_process_code():
    """search 응답에 sub_process_code 포함."""

def test_search_response_includes_risk_level():
    """search 응답에 risk_level 포함 (LR/MR/HR/SR)."""

def test_search_response_includes_assertions():
    """search 응답에 assertions 배열 포함."""
    # 통제의 ControlAssertion 매핑 확인

def test_search_response_no_n_plus_one():
    """JOIN 으로 한 쿼리 — SQL 카운트 검증."""

def test_other_endpoints_unchanged():
    """GET /controls 등 다른 엔드포인트 응답 형식 변경 없음 (회귀 보호)."""
```

→ 기존 18개 + 신규 6개 = **24개**.

---

## 7. 진행 단계

| Step | 작업 | 시간 |
|---|---|---|
| 1 | schemas/rcm.py 에 ControlSearchOut, ControlSearchResponse 추가 | 10분 |
| 2 | api/rcm.py 의 search_controls 함수 JOIN + 매핑 수정 | 20분 |
| 3 | pytest 6개 추가 | 15분 |
| 4 | 사이냅소프트 양식 회귀 테스트 | 5분 |
| **합계** | **약 50분** |

---

## 8. 검증 체크리스트

- [ ] `GET /api/rcm/controls/search` 응답에 4개 신규 필드 포함
- [ ] `GET /api/rcm/controls` 등 다른 엔드포인트 응답 변경 없음 (회귀 보호)
- [ ] JOIN 으로 한 쿼리만 발생 (N+1 회피)
- [ ] pytest 24개 모두 통과
- [ ] 사이냅소프트 95통제로 search 호출 시 정상 응답
- [ ] **ADR-0020 준수**: 추상화·서비스 클래스 0개

---

## 9. ClaudeICFR.md 갱신

### 9.1 섹션 14 (변경 로그) 최상단

```markdown
- **2026-06-02 / TrustBuilder + Claude** — `ControlSearchOut` 스키마 신규. search 엔드포인트 응답에 process_code·sub_process_code·risk_level·assertions 4개 필드 추가 (Regina FE 요청). JOIN 으로 N+1 회피. 기존 ControlOut 보존 (다른 엔드포인트 회귀 안전). pytest +6 = 24개.
```

### 9.2 섹션 18 (일일 로그)

```markdown
- **TrustBuilder**: search 응답 확장 (Regina 제안). 통제 목록 한 번에 받도록. Phase 1 협업 룰 실제 적용 첫 사례.
```

---

## 10. 사용자 OK 후 push

```bash
git add -A
git commit -m "feat(backend): ControlSearchOut 스키마 추가 — search 응답에 process/sub_process/risk_level/assertions 포함"
git push origin main
```
