# ICFR_frontend_8_20260602.md — Phase 1: Excel 업로드 needs_expansion 응답 처리 UI

## 메타 정보

| 항목 | 값 |
|---|---|
| 작업 일시 | 2026-06-02 |
| 작업 유형 | Excel 업로드 시 백엔드의 `status: "needs_expansion"` 응답 처리 — 사용자 확인 후 expand_to 파라미터로 재시도 |
| 담당 | Regina |
| Phase | Phase 1 — 프론트엔드 RCM 작업6 |
| 결정 출처 | claude.ai 사전 승인 (2026-06-02) |
| 예상 작업 시간 | 1~1.5시간 |
| 영향 파일 | `frontend/src/features/rcm/` 내 `uploadExcel.ts` 수정 + `ExcelUploadDialog.tsx` 수정 |
| 커밋 메시지 제안 | `feat(frontend): Excel 업로드 needs_expansion 응답 처리 + 확장 검색 UI` |
| 브랜치 | `feature/fe-rcm-excel-expansion` (ADR-0017 명명 규칙) |

---

## 사전 승인된 결정사항

| 항목 | 결정 |
|---|---|
| 동작 방식 | **수동 확인** — 단계마다 사용자에게 "더 확장 검색할까요?" 확인 |
| UI 위치 | **Dialog 내부 preview 단계 영역** — 별도 Dialog 띄우지 않음 |
| 재시도 횟수 | 최대 2번 (15 → 30, 30 → 130). 그 이후는 백엔드가 `header_not_found` 반환 |
| `expand_param` 필드 | 무시. `next_range` 숫자만 사용해서 직접 Form 필드 구성 |

---

## 작업 지시

`ClaudeICFR.md` (섹션 4.2 RCM 명세), `CLAUDE.md` (섹션 9), 협업자(TrustBuilder)가 알려준 백엔드 동작 명세를 정확히 따라 구현해줘.

**작업 시작 전 필수 체크**:
1. `git fetch origin && git checkout main && git pull` 으로 최신 상태 확인
2. `feature/fe-rcm-excel-expansion` 브랜치 생성
3. 백엔드 컨테이너 healthy 확인 (`docker-compose ps`)
4. 기존 `frontend/` 빌드 통과 확인

---

## 1. 백엔드 응답 명세 (협업자 확인 완료)

### 1.1 `POST /api/rcm/upload-excel` 요청

`multipart/form-data`:
- `file`: Excel 파일
- `mode`: `"preview"` 또는 `"commit"`
- `expand_to` (옵션): `int = 15` (기본). 확장 검색 시 `30` 또는 `130` 전달

### 1.2 가능한 응답 형태

**(A) 정상 미리보기**: HTTP 200, 기존과 동일 (`total_rows`, `preview`, ... 등)

**(B) needs_expansion**: HTTP 200, 추가 처리 필요
```json
{
  "status": "needs_expansion",
  "message": "1~15행에서 RCM 헤더를 찾지 못했습니다. 16~30행까지 확장 검색할까요?",
  "current_range": 15,
  "next_range": 30,
  "expand_param": "?expand_to=30",
  "sheets_checked": ["Sheet1", "RCM"]
}
```

**(C) 최종 실패 (header_not_found)**: HTTP 422
- `status: "header_not_found"` (이미 130행까지 다 봐도 못 찾음)
- 기존 오류 처리 흐름으로 빠짐

### 1.3 핵심 동작

- `status` 필드가 `"needs_expansion"`이면 사용자에게 확장 검색 여부 묻는 카드 표시
- "확장 검색하기" 클릭 → 같은 파일에 `expand_to: <next_range>` Form 필드 붙여서 재요청
- 이 흐름은 **재귀**: 30에서도 needs_expansion 나오면 130까지 확장 → 그래도 못 찾으면 header_not_found

---

## 2. 타입 정의 수정 (`uploadExcel.ts`)

기존 응답 타입을 union으로 확장:

```typescript
// 기존 정상 미리보기 응답 타입
export interface ExcelPreviewSuccess {
  status?: 'ok'              // 백엔드가 명시적으로 안 줄 수도 있음 — 그땐 status 없는 것이 정상 케이스
  total_rows: number
  preview: ExcelPreviewItem[]
  error_count: number
  duplicate_count: number
  ready_to_commit: number
}

// 신규: 확장 필요 응답
export interface ExcelPreviewNeedsExpansion {
  status: 'needs_expansion'
  message: string
  current_range: number
  next_range: number
  expand_param: string        // 힌트 문자열, 무시
  sheets_checked: string[]
}

// union
export type ExcelPreviewResponse = ExcelPreviewSuccess | ExcelPreviewNeedsExpansion

// type guard
export function isNeedsExpansion(
  res: ExcelPreviewResponse
): res is ExcelPreviewNeedsExpansion {
  return (res as ExcelPreviewNeedsExpansion).status === 'needs_expansion'
}
```

> 백엔드 코드 확인 후 정상 응답에 `status: "ok"`가 있는지 확실히 — 없으면 위처럼 옵셔널 처리, 있으면 명시.

### previewExcel 함수 시그니처 변경

```typescript
export async function previewExcel(
  file: File,
  expandTo?: number    // 선택적 파라미터 — needs_expansion 재시도 시 사용
): Promise<ExcelPreviewResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('mode', 'preview')
  if (expandTo !== undefined) {
    formData.append('expand_to', String(expandTo))
  }
  const res = await axiosInstance.post<ExcelPreviewResponse>(
    '/api/rcm/upload-excel',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
  return res.data
}
```

`commitExcel` 함수에도 같은 방식으로 `expandTo` 옵셔널 파라미터 추가 (commit 단계에서도 동일 expand_to 사용해야 함 — 그래야 백엔드가 같은 행을 헤더로 인식).

---

## 3. ExcelUploadDialog.tsx 수정

### 3.1 상태 관리 추가

기존 step 타입에 `'needsExpansion'` 추가:
```typescript
type Step = 'select' | 'previewing' | 'preview' | 'needsExpansion' | 'committing' | 'done' | 'error'
```

신규 상태:
```typescript
const [expansionInfo, setExpansionInfo] = useState<ExcelPreviewNeedsExpansion | null>(null)
const [currentExpandTo, setCurrentExpandTo] = useState<number | undefined>(undefined)
// currentExpandTo는 commit 단계에서도 사용해야 함
```

### 3.2 미리보기 응답 처리 변경

기존:
```typescript
const result = await previewExcel(file)
setPreviewData(result)
setStep('preview')
```

변경:
```typescript
const result = await previewExcel(file, currentExpandTo)
if (isNeedsExpansion(result)) {
  setExpansionInfo(result)
  setStep('needsExpansion')
} else {
  setPreviewData(result)
  setStep('preview')
}
```

### 3.3 `needsExpansion` 단계 UI

Dialog 본문에 새 화면. 카드 형태로 안내:

```
┌────────────────────────────────────────────────────────┐
│  🔍 RCM 헤더를 찾는 중                                  │
│                                                         │
│  {expansionInfo.message}                                │
│  (예: "1~15행에서 RCM 헤더를 찾지 못했습니다.           │
│        16~30행까지 확장 검색할까요?")                   │
│                                                         │
│  확인한 시트: {sheets_checked.join(', ')}              │
│                                                         │
│  ───────────────────────────────                       │
│                                                         │
│  💡 안내                                                │
│  Excel 파일 상단에 빈 행이 많으면 헤더 인식이 어려울    │
│  수 있어요. 확장 검색을 진행하면 더 넓은 범위에서       │
│  헤더를 찾습니다.                                       │
└────────────────────────────────────────────────────────┘

  [취소]    [확장 검색 (1~{next_range}행)]
```

UI 요소:
- 상단: 돋보기 아이콘(`Search` from lucide) + "RCM 헤더를 찾는 중" 제목
- 백엔드 message 그대로 표시 (이미 사용자 친화적 문구라 가공 불필요)
- `sheets_checked` 시트 목록 표시 — 사용자가 어떤 시트를 검사했는지 알 수 있음
- 안내 박스(파란색 또는 회색): 사용자가 다음에 파일을 만들 때 도움 되는 정보
- 하단 버튼:
  - "취소": Dialog 닫기 + 모든 상태 초기화
  - "확장 검색 ({next_range}행까지)": 클릭 시 `currentExpandTo = next_range` 세팅 후 `step = 'previewing'` 으로 변경하고 다시 `previewExcel(file, next_range)` 호출

### 3.4 확장 검색 핸들러

```typescript
async function handleExpand() {
  if (!expansionInfo) return
  const nextRange = expansionInfo.next_range
  setCurrentExpandTo(nextRange)
  setStep('previewing')
  try {
    const result = await previewExcel(file!, nextRange)
    if (isNeedsExpansion(result)) {
      setExpansionInfo(result)
      setStep('needsExpansion')
    } else {
      setPreviewData(result)
      setStep('preview')
    }
  } catch (err) {
    setErrorMessage(extractErrorMessage(err))
    setStep('error')
  }
}
```

### 3.5 commit 단계도 expand_to 전달

`commitExcel`에도 `currentExpandTo` 함께 전달:

```typescript
async function handleCommit() {
  setStep('committing')
  try {
    const result = await commitExcel(file!, currentExpandTo)
    setCommitResult(result)
    setStep('done')
  } catch (err) {
    setErrorMessage(extractErrorMessage(err))
    setStep('error')
  }
}
```

이유: 백엔드가 미리보기와 commit에서 헤더 위치를 다시 탐색하기 때문에, commit에도 같은 `expand_to`를 보내야 같은 헤더 행을 인식.

### 3.6 상태 초기화

Dialog가 닫힐 때(`open=false`) 또는 "취소" 버튼 클릭 시:
- `file`, `previewData`, `expansionInfo`, `currentExpandTo`, `errorMessage` 모두 초기화
- `step = 'select'`로 리셋

`onOpenChange(false)` 핸들러에서 처리.

---

## 4. 백엔드 응답 status: "header_not_found" 처리

협업자 안내에 따르면 HTTP 422로 옴 → 이미 기존 axios 인터셉터/error 핸들러가 잡음. `extractErrorMessage` 함수가 `error.response?.data?.detail` 또는 `message` 등에서 메시지 뽑아내는지 확인. 안 되면 보강.

오류 화면에서 메시지가 명확하게 표시되도록만 확인하면 됨 (별도 새 화면 안 만들어도 됨).

---

## 5. 완료 후 필수 작업

### 5.1 ClaudeICFR.md 업데이트
- **섹션 12.2**: RCM FE 비고에 "Excel 확장 검색 처리" 추가
- **섹션 14**: "Regina: Excel 업로드 needs_expansion 응답 처리 + 확장 검색 UI 추가" 한 줄
- **섹션 18.2**: 일일 진행 로그 추가 (2026-06-02)

### 5.2 git 작업

```bash
git checkout -b feature/fe-rcm-excel-expansion
# (작업 수행)
git add frontend/ ClaudeICFR.md prompts/ICFR_frontend_8_20260602.md
git commit -m "feat(frontend): Excel 업로드 needs_expansion 응답 처리 + 확장 검색 UI"
git push -u origin feature/fe-rcm-excel-expansion
```

> 커밋 메시지는 한 줄 단순 형식 (Windows PowerShell 호환).

### 5.3 동작 확인 체크리스트
- [ ] `npm run build` 통과
- [ ] 정상 Excel 파일 업로드 → 기존처럼 preview 표시
- [ ] 헤더가 16~30행에 있는 Excel 파일 업로드 → "확장 검색할까요?" 카드 표시
- [ ] "확장 검색" 클릭 → expand_to=30으로 재요청 → 정상 preview 표시
- [ ] 헤더가 31~130행에 있는 파일 → 2번 확장 후 정상 preview 표시
- [ ] 헤더가 130행 이후에 있거나 아예 없는 파일 → header_not_found 오류 메시지 명확히 표시
- [ ] commit 단계에서 동일한 expand_to 전달되는지 확인 (Network 탭)
- [ ] 확장 검색 진행 중 "취소" 클릭 → Dialog 닫힘 + 상태 초기화
- [ ] Dialog 다시 열면 select 단계부터 시작 (이전 expand_to 영향 없음)

---

## 6. 테스트 시 주의사항

이번 작업의 단점: **needs_expansion 케이스를 재현하려면 헤더가 16행 이후에 있는 Excel 파일이 필요**. Regina가 직접 그런 테스트 파일 만들 수 있어요:
- 기존 정상 파일의 행 1~15에 빈 행 추가 → 헤더가 16행 이후로 밀림
- 또는 협업자에게 테스트 케이스 파일 요청

만약 테스트 파일 없으면 정상 동작(기존 preview)만 확인하고 push해도 OK. needs_expansion 처리는 백엔드 명세대로 구현됐다면 정상 동작할 가능성이 높음.

---

## 7. 작업 외 (다음 작업으로 미룸)

- useControls mock → API 전환 (협업자 4개 필드 추가 후 진행)
- 통제 추가/편집 API 연결
- 위험 매트릭스 시각화

---

## 8. 참조

- Excel 업로드 API: `backend/app/api/rcm.py` 의 `/upload-excel`
- needs_expansion 응답 명세: 협업자(TrustBuilder) 보고 (2026-06-02)
- 협업 분담: ADR-0017
- 이전 작업: `prompts/ICFR_frontend_7_20260601.md` (보류 — 협업자 작업 대기)
- 관련 이전: `prompts/ICFR_frontend_6_20260530.md` (Excel 업로드 첫 구현)
