# ICFR_frontend_6_20260530.md — Phase 1: RCM Excel 업로드 (진짜 백엔드 API 첫 연결)

## 메타 정보

| 항목 | 값 |
|---|---|
| 작업 일시 | 2026-05-30 |
| 작업 유형 | RCM Excel 업로드 (preview → commit 2단계) + 첫 진짜 백엔드 API 연결 |
| 담당 | Regina |
| Phase | Phase 1 — 프론트엔드 RCM 작업4 |
| 결정 출처 | claude.ai 사전 승인 (2026-05-30) |
| 예상 작업 시간 | 2~3시간 (첫 API 연결이라 트러블슈팅 여유 포함) |
| 영향 파일 | `frontend/src/features/rcm/` 내 신규 약 3~5개 + ControlTable·RcmPage 수정 + axios 인스턴스 점검 |
| 커밋 메시지 제안 | `feat(frontend): RCM Excel 업로드 (preview/commit) + 첫 백엔드 API 연결` |
| 브랜치 | `feature/fe-rcm-excel-upload` (ADR-0017 명명 규칙) |

---

## 사전 승인된 결정사항

| 항목 | 결정 |
|---|---|
| 데이터 방식 | **진짜 백엔드 API 연결** (첫 시도) — `POST /api/rcm/upload-excel` |
| 진입 위치 | RCM 목록 화면 우상단 — "+ 통제 추가" 버튼 옆에 "Excel 업로드" 버튼 추가 |
| 흐름 | 파일 선택 → preview 호출 → 결과 확인 → commit 호출 → 목록 갱신 |

---

## 작업 지시

`ClaudeICFR.md` (섹션 4.2 RCM 명세, 섹션 19 API 명세 표준),
`CLAUDE.md` (섹션 9 명세 동기화 체크),
`backend/app/api/rcm.py`의 `/upload-excel` 엔드포인트 구현을 먼저 확인하고, 아래를 구현해줘.

**작업 시작 전 필수 체크 (CLAUDE.md 섹션 9)**:
1. `git fetch origin && git checkout main && git pull` 으로 최신 상태 확인
2. **이전 작업(`feature/fe-rcm-edit`) 머지 여부 확인** — 미머지면 머지 협의 후 main에서 분기
3. `feature/fe-rcm-excel-upload` 브랜치 생성
4. 백엔드 컨테이너 실행 중 확인 (`docker-compose ps` — backend healthy 필요)
5. `frontend/src/lib/axios.ts` 인터셉터(인증 토큰·refresh) 정상 동작 확인

---

## 1. 백엔드 API 확인 (코드 읽고 정확히 매칭할 것)

`backend/app/api/rcm.py` 의 `/upload-excel` 엔드포인트를 먼저 열어 다음을 확인:
- 요청 방식: `multipart/form-data` (file + mode)
- `mode=preview` 와 `mode=commit` 응답 형태
- 미리보기 응답에 어떤 필드가 들어오는지 (최대 20건)
- commit 응답: 저장 건수, 스킵 건수, 에러 등
- 에러 응답 형식 (HTTP 4xx 시 `detail` 필드 등)

> 백엔드 코드와 100% 매칭되는 타입 정의를 만든다. 추측 금지.

---

## 2. 핵심 설계 원칙

- **mock 코드와 실제 API 코드를 한 파일에서 동시 관리하지 않는다** — Excel 업로드 전용 함수는 처음부터 axios로 작성
- **axios 인스턴스 재사용**: `frontend/src/lib/axios.ts` 의 기존 인스턴스 사용 (인증 헤더·refresh 자동 처리)
- **에러 핸들링 명확히**: 네트워크 오류 / 401 / 422 / 500 모두 사용자에게 적절한 메시지로
- **commit 성공 후 목록 갱신**: `useControls`가 mock 상태를 보여주고 있으므로, commit 후엔 mock도 함께 갱신할지 결정 필요 → **목록 새로고침 트리거 + 안내 토스트로 처리** (다음 작업에서 useControls를 전면 API화)

---

## 3. 생성/수정 파일 구조

```
frontend/src/features/rcm/
├── api/
│   └── uploadExcel.ts            ← 신규: axios 기반 업로드 함수
├── components/
│   ├── ExcelUploadDialog.tsx     ← 신규: 업로드 Dialog (선택 → preview → commit)
│   ├── ExcelPreviewTable.tsx     ← 신규: preview 결과 미리보기 표
│   └── ControlTable.tsx          ← 수정: "Excel 업로드" 버튼 추가
└── pages/
    └── RcmPage.tsx               ← 수정: uploadDialog state + 핸들러
```

---

## 4. API 호출 함수 (api/uploadExcel.ts)

```typescript
import axiosInstance from '@/lib/axios'

export interface ExcelPreviewItem {
  // 백엔드 응답 스키마 그대로 매칭. backend/app/api/rcm.py 확인 후 정확히 적을 것.
  // 예시 (백엔드 코드 확인 후 보정):
  row_number: number
  control_code: string
  control_name: string
  process_code: string | null
  sub_process_code: string | null
  risk_level: string | null
  // ... 백엔드가 반환하는 모든 필드
  errors?: string[]   // 행별 검증 오류 (있을 때만)
}

export interface ExcelPreviewResponse {
  total_rows: number
  preview: ExcelPreviewItem[]   // 최대 20건
  error_count: number
  duplicate_count: number       // 이미 DB에 존재하는 code 수
  ready_to_commit: number       // 저장 가능한 건수
}

export interface ExcelCommitResponse {
  total: number
  inserted: number
  skipped: number
  errors: number
  message?: string
}

export async function previewExcel(file: File): Promise<ExcelPreviewResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('mode', 'preview')
  const res = await axiosInstance.post<ExcelPreviewResponse>(
    '/api/rcm/upload-excel',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
  return res.data
}

export async function commitExcel(file: File): Promise<ExcelCommitResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('mode', 'commit')
  const res = await axiosInstance.post<ExcelCommitResponse>(
    '/api/rcm/upload-excel',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
  return res.data
}
```

> **주의**: 정확한 스키마는 `backend/app/api/rcm.py` 와 `backend/app/schemas/rcm.py` (또는 응답 모델 위치) 확인 후 보정. 위는 예상치임.

---

## 5. ExcelUploadDialog.tsx — 업로드 흐름

shadcn `Dialog` 사용 (이미 설치됨). 너비 넓게 (`max-w-4xl`).

**단계별 상태:**
```typescript
type Step = 'select' | 'previewing' | 'preview' | 'committing' | 'done' | 'error'
```

### 단계 1: select (파일 선택)
- 파일 드롭존 + "파일 선택" 버튼
- 허용 확장자 안내: `.xlsx`, `.xls` (지원 형식은 백엔드 확인)
- 선택된 파일명 표시
- "양식 다운로드" 안내 링크 (현재는 텍스트만 — 추후 협업자에게 양식 위치 확인)
- "미리보기" 버튼 → `previewExcel(file)` 호출 → `previewing` 단계

### 단계 2: previewing (로딩)
- Spinner + "Excel 분석 중..." 메시지
- 시간 오래 걸리면 안내 ("100건 이상은 잠시 걸릴 수 있습니다")

### 단계 3: preview (미리보기 결과)
상단 요약 카드:
- 전체: `total_rows` 건
- 저장 가능: `ready_to_commit` 건 (초록)
- 중복: `duplicate_count` 건 (노랑)
- 오류: `error_count` 건 (빨강)

그 아래 `ExcelPreviewTable` (다음 섹션):
- 최대 20건 표시 (`preview` 배열)
- 오류 행은 빨강 배경, errors[] 내용 표시

하단 버튼:
- "취소" → 처음으로
- "등록" (저장 가능 건수가 0이면 비활성) → `commitExcel(file)` 호출 → `committing` 단계

### 단계 4: committing (저장 중)
- Spinner + "저장 중... ({total}건)" 메시지

### 단계 5: done (완료)
- 결과 요약:
  - 저장됨: inserted 건
  - 스킵됨(중복): skipped 건
  - 오류: errors 건
- "확인" 버튼 → Dialog 닫기 + 부모에 `onSuccess` 콜백 → 목록 새로고침

### 단계 6: error (네트워크/서버 오류)
- 오류 메시지 표시 (`error.response?.data?.detail` 또는 일반 메시지)
- "다시 시도" / "닫기" 버튼

---

## 6. ExcelPreviewTable.tsx — 미리보기 표

작은 테이블로 표시. 컬럼:
- 행 번호 (`row_number`)
- 통제 코드 (`control_code`)
- 통제명 (`control_name`)
- 프로세스 / 세부 / 위험수준
- 상태 — 신규 저장 / 중복(스킵) / 오류

오류 행:
- 행 배경 빨강(`bg-red-50`)
- 행 아래 작은 글씨로 errors[] 나열

데이터 없으면: "표시할 항목 없음"

---

## 7. ControlTable.tsx 수정

상단 우측 버튼 영역에 **"Excel 업로드"** 버튼 추가 (lucide `Upload` 아이콘):
```
[Excel 업로드] [+ 통제 추가]
```

- variant="outline" 정도로 + 통제 추가와 시각적 위계 구분
- 클릭 시 `onUploadClick()` 콜백 → 부모에서 Dialog 오픈

---

## 8. RcmPage.tsx 수정

상태 추가:
```typescript
const [uploadOpen, setUploadOpen] = useState(false)

function handleUploadClick() {
  setUploadOpen(true)
}

function handleUploadSuccess() {
  setUploadOpen(false)
  toast.success('Excel 업로드가 완료되었습니다')
  // 목록 새로고침 — 현재 useControls는 mock이므로 페이지 새로고침 안내
  // 또는 useControls가 진짜 API라면 invalidate
}
```

JSX:
```tsx
<ControlTable
  ...
  onUploadClick={handleUploadClick}
/>
<ExcelUploadDialog
  open={uploadOpen}
  onOpenChange={setUploadOpen}
  onSuccess={handleUploadSuccess}
/>
```

---

## 9. mock과 실제 API의 간극 처리

**중요**: 현재 RCM 목록은 mock 데이터(`mockControls` 30건)를 보여준다. 그러나 Excel 업로드는 실제 백엔드 DB에 저장한다. 이 간극을 사용자에게 명확히 안내:

ExcelUploadDialog의 "select" 단계 상단에 안내 박스 추가:
```
ⓘ 안내: Excel 업로드는 실제 백엔드 DB에 저장됩니다.
   현재 화면에 보이는 통제 목록(mock 데이터)과는 별도로 저장되며,
   추후 목록도 실제 API로 전환 예정입니다.
```

배경 노란색(`bg-yellow-50`), 테두리 노란색.

이 메시지는 다음 작업(useControls API화)에서 제거 예정.

---

## 10. CORS·인증 트러블슈팅 가이드

진짜 API 첫 연결이라 다음 문제가 발생할 수 있다. 미리 점검:

1. **CORS 오류** (`Access-Control-Allow-Origin`):
   - `vite.config.ts` 에 proxy 설정 (`'/api' → 'http://localhost:8000'`) 확인
   - 또는 백엔드 CORS 미들웨어 허용 도메인에 `http://localhost:5173` 포함 확인

2. **401 Unauthorized**:
   - 로그인 안 한 상태에서 업로드 시도 시 발생
   - axios 인터셉터가 refresh → 재시도하는지 확인
   - 로그인 후 토큰이 `localStorage`에 저장됐는지 확인

3. **422 Validation Error**:
   - FormData 필드명·mode 값(`preview` / `commit`)이 백엔드 요구와 정확히 일치하는지 확인

4. **파일 크기/형식 오류**:
   - 백엔드가 받는 최대 파일 크기 확인 (보통 nginx·FastAPI 기본 약 10MB)
   - 확장자 검증

문제 발생 시 브라우저 개발자 도구(F12) Network 탭에서 실제 요청·응답 확인.

---

## 11. 완료 후 필수 작업

### 11.1 ClaudeICFR.md 업데이트
- **섹션 12.2**: RCM FE 컬럼 → 비고에 "Excel 업로드(API 연결)" 추가
- **섹션 14**: "Regina: Phase 1 RCM Excel 업로드 — 첫 진짜 API 연결 완료" 한 줄
- **섹션 18.2**: 일일 진행 로그 (2026-05-30)

### 11.2 git 작업

```bash
git checkout -b feature/fe-rcm-excel-upload
# (작업 수행)
git add frontend/ ClaudeICFR.md prompts/ICFR_frontend_6_20260530.md
git commit -m "feat(frontend): RCM Excel 업로드 (preview/commit) + 첫 백엔드 API 연결"
git push -u origin feature/fe-rcm-excel-upload
```

> 커밋 메시지는 heredoc 없이 한 줄로 단순하게 작성할 것 (Windows PowerShell 호환).

### 11.3 동작 확인 체크리스트
- [ ] `npm run build` 통과 (TypeScript 오류 없음)
- [ ] 백엔드 컨테이너 healthy 상태
- [ ] 로그인 후 RCM 화면 우상단에 "Excel 업로드" 버튼 표시
- [ ] 버튼 클릭 → Dialog 열림, 노란색 안내 박스 표시
- [ ] 파일 선택 후 "미리보기" → 백엔드 응답 받아 미리보기 표시
- [ ] 미리보기 요약(전체/저장가능/중복/오류) 정확히 표시
- [ ] 오류 행 빨간 배경 + 오류 내역 표시
- [ ] "등록" 클릭 → commit 호출 → 결과 요약 표시
- [ ] "확인" 클릭 → Dialog 닫힘 + 성공 토스트
- [ ] 잘못된 파일(엉뚱한 형식) 업로드 시 적절한 오류 메시지
- [ ] 백엔드 꺼진 상태에서 업로드 시도 → "서버 연결 실패" 등 명확한 메시지

### 11.4 테스트용 Excel 양식

- 협업자(TrustBuilder)가 만든 사이냅소프트 양식이 어딘가에 있을 가능성 높음 — `backend/tests/` 또는 `backend/app/seeds/` 폴더 확인
- 없으면 협업자에게 샘플 Excel 파일 요청
- 임시로는 빈 Excel 파일(.xlsx) 만들어 "잘못된 형식" 오류 메시지 동작 확인 가능

---

## 12. 작업 외 (다음 작업으로 미룸)

- 위험 매트릭스 시각화
- `useControls` 훅을 mock → 실제 API로 전환 (목록·검색·페이지네이션 모두 백엔드 호출로)
- 다건 삭제 (bulk-delete API 연결)
- 통제 추가/편집도 실제 API 연결 (addControl/updateControl 교체)

---

## 13. 참조

- RCM 모듈 명세: `ClaudeICFR.md` 섹션 4.2
- 백엔드 Excel 업로드 API: `backend/app/api/rcm.py` 의 `/upload-excel`
- 백엔드 스키마: `backend/app/schemas/rcm.py`
- axios 인스턴스: `frontend/src/lib/axios.ts`
- 협업 분담: ADR-0017
- 이전 작업: `prompts/ICFR_frontend_5_20260530.md` (통제 추가/편집 폼)
- 다음 작업: `ICFR_frontend_7` (useControls 전체 API화 또는 다음 모듈)
