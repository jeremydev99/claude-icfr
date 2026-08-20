# ICFR-13.6 Excel 멀티헤더 파싱 버그 — 조사 전용

## 목적
Excel 업로드 멀티헤더 파싱 버그의 **정확한 위치·원인·재현 조건**을 파악한다.
이번 작업은 **조사(read-only)만** 한다. 구현/수정/커밋 없음.

## 스코프 가드 (엄수)
- 코드 **수정 금지**. 파일 열람·검색만.
- 파싱 로직 파일은 **필요한 부분만 짧게** 읽는다(전체 통독 금지).
- 새 파일 생성·삭제 금지. git 조작 금지.
- 백엔드가 파싱 주체로 확인되면 **거기서 멈추고 보고만** 한다(백엔드는 TrustBuilder 트랙).

## 조사 항목 (순서대로)

### 1. 파싱 위치 확정 (FE인가 BE인가)
- 프론트에서 SheetJS(xlsx) import 및 헤더 파싱하는 지점 검색
  - `Select-String -Path src\**\*.ts,src\**\*.tsx -Pattern "xlsx|sheet_to_json|SheetJS|read.*workbook" -List`
- Excel 업로드 API 호출 경로 확인 (FE가 파일을 그대로 백엔드로 넘기는지, FE에서 파싱 후 JSON을 넘기는지)
  - 업로드 관련 컴포넌트/훅에서 `FormData` vs 파싱된 payload 여부 확인
- **결론:** 멀티헤더 파싱 실제 주체가 FE인지 BE인지 한 줄로 명시

### 2. EXCEL_UPLOAD_LOCKED 잠금 지점 확인
- `Select-String -Path src\**\*.ts,src\**\*.tsx -Pattern "EXCEL_UPLOAD_LOCKED" -List`
- 잠금이 어디서 걸려 UI를 막는지, 파싱 로직과의 관계 확인

### 3. 멀티헤더 구조 유형 파악
- RCM 엑셀 헤더가 아래 중 무엇 때문에 깨지는지 확인:
  - (a) 2행(2-row) 헤더 — 상위 그룹 라벨 + 하위 컬럼 라벨
  - (b) 병합셀(merged cell) 헤더
  - (c) Process/Sub-Process/Risk/Control 계층 그룹 헤더
- 파싱 코드가 헤더를 **몇 번째 행부터** 읽는지(`range`, `header` 옵션 등) 확인
- 실패 지점: 어느 컬럼/행에서 매핑이 깨지거나 빈 값/undefined가 생기는지

### 4. 재현 조건 정리
- 어떤 헤더 구조의 엑셀이 들어오면 깨지는지 최소 재현 케이스 서술
- 정상 파싱되는 케이스와의 차이

## 산출물 (보고 형식)
아래를 채워서 보고만 할 것. 코드는 고치지 말 것.
1. 파싱 주체: FE / BE (근거 파일:라인)
2. 잠금 지점: EXCEL_UPLOAD_LOCKED 위치와 역할
3. 멀티헤더 유형: (a)/(b)/(c) 중 무엇, 근거
4. 깨지는 정확한 지점: 파일:라인 + 증상
5. 최소 재현 조건
6. 픽스가 FE 트랙인지 BE(TrustBuilder) 트랙인지 판단

## PowerShell 5.1 제약
- `&&` 금지 → `;` 또는 명령 분리
- `grep` 금지 → `Select-String`
- `cd` 금지 → `Set-Location E:\claudeprojects\ICFR`
- bash 경로·heredoc·`2>&1` 금지
- 단일 명령 965 bytes 이내

---
ICFR-13.6-excel-multiheader-investigate.md 진행해줘
