# ICFR_frontend_5_20260530.md — Phase 1: RCM 통제 추가/편집 폼 (mock 데이터)

## 메타 정보

| 항목 | 값 |
|---|---|
| 작업 일시 | 2026-05-30 |
| 작업 유형 | RCM 통제 추가/편집 폼 — Dialog + 4탭 + React Hook Form + Zod |
| 담당 | Regina |
| Phase | Phase 1 — 프론트엔드 RCM 작업3 |
| 결정 출처 | claude.ai 사전 승인 (2026-05-30) |
| 예상 작업 시간 | 1.5~2.5시간 |
| 영향 파일 | `frontend/src/features/rcm/` 내 신규 약 5~7개 + ControlTable·RcmPage·ControlDetailSheet 수정 |
| 커밋 메시지 제안 | `feat(frontend): RCM 통제 추가/편집 폼 — Dialog + 4탭 (mock 데이터)` |
| 브랜치 | `feature/fe-rcm-edit` (ADR-0017 명명 규칙) |

---

## 사전 승인된 결정사항

| 항목 | 결정 |
|---|---|
| 편집 화면 방식 | shadcn/ui `Dialog` 팝업 (상세 패널과 분리) |
| 입력 레이아웃 | `Tabs` 4개 — 기본 정보 / 분류 / 활동 유형 / 관련 정보 |
| 작업 범위 | 추가 + 편집 둘 다 (동일 컴포넌트가 mode 전환) |
| 데이터 방식 | mock (`useControls` 데이터에 추가/수정 — 메모리 상태만 변경, 새로고침 시 초기화됨을 사용자에게 안내) |
| 폼 검증 | React Hook Form + Zod |

---

## 작업 지시

`ClaudeICFR.md` (섹션 4.2 RCM 명세, 섹션 14 변경 로그, ADR-0017),
`CLAUDE.md` (섹션 9 명세 동기화 체크)를 먼저 확인하고, 아래 통제 추가/편집 폼을 구현해줘.

**작업 시작 전 필수 체크 (CLAUDE.md 섹션 9)**:
1. `git fetch origin && git checkout main && git pull` 으로 최신 상태 확인
2. `feature/fe-rcm-edit` 브랜치 생성
3. 기존 `frontend/` 빌드 정상 동작 확인 (`npm run build`)
4. 직전 작업(상세보기 패널)이 main에 포함돼 있는지 확인

---

## 1. 핵심 설계 원칙

- **하나의 컴포넌트로 추가/편집 모두 처리**: `ControlFormDialog`. `mode: 'create' | 'edit'` props로 분기
- **mock 데이터 변경**: `useControls` 훅에 `addControl`, `updateControl` 함수 추가. 클라이언트 메모리(useState 또는 모듈 변수)에만 반영 — 새로고침 시 초기 30건으로 복원됨을 폼 하단에 안내 문구 표시
- **나중에 진짜 API 교체 지점**: `addControl`/`updateControl` 함수 내부만 `POST /api/rcm/controls` / `PATCH /api/rcm/controls/{id}` 로 교체
- **검증은 Zod 스키마로**: 백엔드 스키마 제약과 일치 (코드 필수, name 필수 등)
- **폼 상태 관리**: React Hook Form 사용 (`useForm`, `Controller`)

---

## 2. 생성/수정 파일 구조

```
frontend/src/features/rcm/
├── api/
│   └── useControls.ts            ← 수정: addControl, updateControl 함수 노출
├── components/
│   ├── ControlFormDialog.tsx     ← 신규: 추가/편집 Dialog (4탭 폼)
│   ├── form-tabs/
│   │   ├── BasicInfoTab.tsx      ← 신규: 기본 정보 탭
│   │   ├── ClassificationTab.tsx ← 신규: 통제 분류 탭
│   │   ├── ActivityTab.tsx       ← 신규: 활동 유형 탭
│   │   └── RelatedInfoTab.tsx    ← 신규: 관련 정보 탭
│   ├── ControlTable.tsx          ← 수정: "통제 추가" 버튼 + 행에 "편집" 액션
│   └── ControlDetailSheet.tsx    ← 수정: "편집" 버튼 실제 동작 연결
└── pages/
    └── RcmPage.tsx               ← 수정: formDialog state + 추가/편집 핸들러
```

필요 shadcn 컴포넌트: `dialog`, `tabs`, `textarea`. 없으면 설치:
```bash
npx shadcn@latest add dialog tabs textarea
```

---

## 3. mock 데이터 수정 (api/useControls.ts)

기존 훅을 확장해서 추가/수정 함수를 노출.

```typescript
// 모듈 전역 변수로 mock 데이터 보관 (페이지 유지되는 동안)
// 새로고침 시에는 mockData.ts 초기값으로 리셋됨
let controlsState: Control[] = [...mockControls]
const subscribers = new Set<() => void>()

function notify() {
  subscribers.forEach(fn => fn())
}

export function useControls(params: ControlSearchParams): {
  data: ControlListResponse
  isLoading: boolean
} {
  const [, forceRender] = useState(0)
  useEffect(() => {
    const sub = () => forceRender(n => n + 1)
    subscribers.add(sub)
    return () => { subscribers.delete(sub) }
  }, [])
  // 기존 필터·정렬·페이지네이션 로직은 controlsState 기준으로 동작
  // ...
}

// TODO: replace with `axios.post('/api/rcm/controls', payload)`
export function addControl(payload: Omit<Control, 'id' | 'created_at'>): Control {
  const newControl: Control = {
    ...payload,
    id: crypto.randomUUID(),
    created_at: new Date().toISOString(),
  }
  controlsState = [newControl, ...controlsState]
  notify()
  return newControl
}

// TODO: replace with `axios.patch('/api/rcm/controls/${id}', payload)`
export function updateControl(id: string, payload: Partial<Control>): Control | null {
  const idx = controlsState.findIndex(c => c.id === id)
  if (idx === -1) return null
  controlsState[idx] = { ...controlsState[idx], ...payload }
  notify()
  return controlsState[idx]
}
```

> 주의: 본 작업은 mock이므로 `controlsState`는 모듈 변수. 다음 작업에서 진짜 API 호출로 바꾸면 `controlsState`는 제거 대상.

---

## 4. Zod 스키마 (ControlFormDialog 내부 또는 별도 schema.ts)

```typescript
import { z } from 'zod'

export const controlFormSchema = z.object({
  // 기본 정보
  code: z.string().min(1, '통제 코드는 필수').max(50),
  name: z.string().min(1, '통제명은 필수').max(200),
  description: z.string().nullable().optional(),
  objective: z.string().nullable().optional(),
  owner_name: z.string().nullable().optional(),
  process_code: z.string().min(1, '프로세스 선택 필요'),
  sub_process_code: z.string().min(1, '세부 프로세스 선택 필요'),
  risk_level: z.enum(['LR', 'MR', 'HR', 'SR']),
  // 분류
  is_key_control: z.boolean(),
  preventive_detective: z.enum(['P', 'D']),
  auto_manual: z.enum(['A', 'M', 'IT']),
  frequency: z.enum(['O', 'D', 'W', 'M', 'Q', 'A']),
  ipe_relevant: z.enum(['Y', 'N', 'N/A']),
  // 활동 (6종 bool)
  activity_approval: z.boolean(),
  activity_verification: z.boolean(),
  activity_inspection: z.boolean(),
  activity_master: z.boolean(),
  activity_reconciliation: z.boolean(),
  activity_supervision: z.boolean(),
  // 어서션
  assertions: z.array(z.enum(['E', 'C', 'R', 'V', 'P', 'O', 'M'])).default([]),
  // 관련 정보
  related_accounts: z.string().nullable().optional(),
  related_systems: z.string().nullable().optional(),
  euc_description: z.string().nullable().optional(),
})

export type ControlFormData = z.infer<typeof controlFormSchema>
```

기본값(추가 모드 진입 시):
```typescript
{
  code: '', name: '', description: '', objective: '', owner_name: '',
  process_code: '', sub_process_code: '', risk_level: 'MR',
  is_key_control: false,
  preventive_detective: 'P', auto_manual: 'M', frequency: 'M', ipe_relevant: 'N/A',
  activity_approval: false, activity_verification: false, activity_inspection: false,
  activity_master: false, activity_reconciliation: false, activity_supervision: false,
  assertions: [],
  related_accounts: '', related_systems: '', euc_description: '',
}
```

---

## 5. ControlFormDialog (components/ControlFormDialog.tsx)

shadcn/ui `Dialog` 사용. 너비 넓게 (`max-w-3xl`).

**Props:**
```typescript
interface ControlFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode: 'create' | 'edit'
  control?: Control          // edit 모드일 때 초기값
  onSuccess?: (saved: Control) => void
}
```

**Dialog 구조:**

```
┌─────────────────────────────────────────────────────────┐
│ 통제 추가 / 통제 편집                              [X]  │   ← DialogHeader
├─────────────────────────────────────────────────────────┤
│ [기본 정보] [분류] [활동 유형] [관련 정보]              │   ← TabsList
│                                                          │
│  (선택된 탭 내용 영역, 최대 높이 + 내부 스크롤)         │
│                                                          │
├─────────────────────────────────────────────────────────┤
│ ⓘ mock 데이터입니다 — 새로고침 시 초기화됩니다.         │
│                              [취소]  [저장]              │   ← DialogFooter
└─────────────────────────────────────────────────────────┘
```

**동작:**
- `mode === 'create'` → 제목 "통제 추가", 폼은 기본값
- `mode === 'edit'` → 제목 "통제 편집", 폼은 `control` 데이터로 채움
- "저장" 클릭:
  1. Zod 검증 (실패 시 해당 탭으로 자동 이동 + 에러 표시)
  2. create면 `addControl(data)`, edit면 `updateControl(control.id, data)`
  3. 성공 시 `onSuccess(saved)` 호출 + Dialog 닫힘 + 토스트 "저장되었습니다"
- "취소" 클릭 → 변경사항 있으면 confirm("저장하지 않고 닫을까요?") 후 닫기

**검증 에러가 다른 탭의 필드일 때**:
- React Hook Form의 `errors` 객체 검사 → 어느 탭에 에러 있는지 매핑
- 첫 에러 필드가 속한 탭으로 자동 이동
- 각 탭 헤더에 에러 개수 빨간 점/배지로 표시 (예: "기본 정보 •")

---

## 6. 각 탭 컴포넌트

### 6.1 BasicInfoTab.tsx (기본 정보)
- 통제 코드 (Input, 필수, edit 모드에서는 readonly로 잠금)
- 통제명 (Input, 필수)
- 통제 목적 (Textarea)
- 담당자명 (Input)
- 프로세스 (Select, 필수) — 옵션: O2C, P2P, R2R, HR, ITG (mockData에서 distinct 추출)
- 세부 프로세스 (Select, 필수) — 선택한 프로세스에 따라 옵션 동적 변경
- 위험 수준 (Select, 필수) — LR/MR/HR/SR + 한글 라벨
- 통제 설명 (Textarea)

### 6.2 ClassificationTab.tsx (분류)
- 핵심통제 여부 (Checkbox 또는 Switch)
- 예방/적발 (RadioGroup 또는 Select)
- 자동/수동 (RadioGroup 또는 Select)
- 수행 주기 (Select)
- IPE 관련성 (Select) — Y / N / N/A
- 어서션 (Multi-select 또는 체크박스 그룹) — E, C, R, V, P, O, M 7개 중 다중 선택 (한글 라벨 함께)

### 6.3 ActivityTab.tsx (활동 유형)
6개 Checkbox 2열 그리드:
- [ ] 승인
- [ ] 검증
- [ ] 실사
- [ ] 마스터
- [ ] 조정
- [ ] 감독

설명 문구: "이 통제에 해당하는 활동 유형을 모두 선택하세요. (복수 선택 가능)"

### 6.4 RelatedInfoTab.tsx (관련 정보)
- 관련 계정 (Textarea)
- 관련 시스템 (Textarea)
- EUC 설명 (Textarea)

---

## 7. ControlTable.tsx 수정

- 상단에 **"+ 통제 추가"** 버튼 (우측 정렬, primary 스타일)
  - 클릭 시 부모(`RcmPage`)에 `onAddClick()` 콜백
- 각 행 끝(또는 별도 액션 컬럼)에 **"편집"** 아이콘 버튼 (lucide `Pencil`)
  - 클릭 시 `onEdit(control)` 콜백 — 행 클릭(상세보기)과 이벤트 버블링 분리 (`e.stopPropagation()`)
- 행 클릭(상세보기) vs 편집 버튼 클릭이 헷갈리지 않도록 편집 버튼 영역만 호버 강조

---

## 8. ControlDetailSheet.tsx 수정

- 우상단 "편집" 버튼이 이제 실제 동작 — 부모로 `onEditClick(control)` 콜백 전파
- "준비중" 안내는 제거
- 편집 버튼 클릭 시: 상세 Sheet 닫고 → 편집 Dialog 열기 (또는 동시 열어두고 Dialog가 위에 표시)

---

## 9. RcmPage.tsx 수정

상태 추가:
```typescript
const [formOpen, setFormOpen] = useState(false)
const [formMode, setFormMode] = useState<'create' | 'edit'>('create')
const [editingControl, setEditingControl] = useState<Control | null>(null)

function handleAddClick() {
  setFormMode('create')
  setEditingControl(null)
  setFormOpen(true)
}

function handleEditClick(control: Control) {
  setFormMode('edit')
  setEditingControl(control)
  setFormOpen(true)
}
```

JSX:
```tsx
<ControlTable
  ...
  onAddClick={handleAddClick}
  onEdit={handleEditClick}
/>
<ControlDetailSheet
  ...
  onEditClick={handleEditClick}
/>
<ControlFormDialog
  open={formOpen}
  onOpenChange={setFormOpen}
  mode={formMode}
  control={editingControl ?? undefined}
/>
```

---

## 10. 토스트 (성공 메시지 표시)

shadcn/ui `Toaster` 추가:
```bash
npx shadcn@latest add sonner
```

`App.tsx` 또는 `main.tsx` 최상위에 `<Toaster />` 배치. 저장 성공 시:
```typescript
import { toast } from 'sonner'
toast.success('저장되었습니다')
```

---

## 11. 완료 후 필수 작업

### 11.1 ClaudeICFR.md 업데이트
- **섹션 12.2**: RCM FE 컬럼/비고에 "목록+검색+상세+편집(mock)" 갱신
- **섹션 14**: "Regina: Phase 1 RCM 통제 추가/편집 폼 (mock) 완료" 한 줄 추가
- **섹션 18.2**: 일일 진행 로그 추가 (2026-05-30)

### 11.2 git 작업

```bash
git checkout -b feature/fe-rcm-edit
# (작업 수행)
git add frontend/ ClaudeICFR.md prompts/ICFR_frontend_5_20260530.md
git commit -m "feat(frontend): RCM 통제 추가/편집 폼 — Dialog + 4탭 (mock 데이터)"
git push -u origin feature/fe-rcm-edit
```

### 11.3 동작 확인 체크리스트
- [ ] `npm run build` 통과 (TypeScript 오류 없음)
- [ ] RCM 목록 우상단에 "+ 통제 추가" 버튼 표시
- [ ] "통제 추가" 클릭 → 빈 폼 Dialog 열림, 탭 4개 표시
- [ ] 필수 필드 비우고 저장 → 검증 오류, 해당 탭으로 자동 이동
- [ ] 모든 필수 입력 후 저장 → 토스트 "저장되었습니다" + 목록 최상단에 새 통제 표시
- [ ] 행 끝 편집 아이콘 클릭 → 편집 Dialog 열림 + 기존 값으로 채워짐
- [ ] 통제 코드 필드는 편집 모드에서 잠금(readonly)
- [ ] 일부 필드 변경 후 저장 → 토스트 + 목록에 반영
- [ ] 상세 패널 우상단 "편집" 클릭 → 편집 Dialog 열림 (상세 Sheet 닫힘)
- [ ] 변경사항 있는 상태에서 취소 시 confirm 표시
- [ ] 페이지 새로고침 시 mock 데이터 초기 30건으로 복원
- [ ] 폼 하단 안내 문구 "mock 데이터입니다 — 새로고침 시 초기화됩니다" 표시

---

## 12. 작업 외 (다음 작업으로 미룸)

- 통제 삭제 (단건 + bulk)
- Excel 업로드 (preview → commit 2단계 UI)
- 위험 매트릭스 시각화
- 실제 API 연동 (addControl/updateControl 내부 교체)
- 변경 이력 표시
- 통제별 평가 결과 연결

---

## 13. 참조

- RCM 모듈 명세: `ClaudeICFR.md` 섹션 4.2
- 백엔드 RCM API: `POST /api/rcm/controls`, `PATCH /api/rcm/controls/{id}` (이번엔 mock으로 흉내만)
- 협업 분담: ADR-0017
- 이전 작업: `prompts/ICFR_frontend_4_20260522.md` (통제 상세보기 패널)
- 다음 작업: `ICFR_frontend_6` (RCM Excel 업로드 또는 다음 모듈로 진행)
