# ICFR_frontend_9_20260611.md — Phase 1: 통제 추가/편집/단건 삭제 실 API 전환

## 메타 정보

| 항목 | 값 |
|---|---|
| 작업 일시 | 2026-06-11 |
| 작업 유형 | RCM 통제 추가/편집/삭제 mock → 백엔드 실 API 전환 (TanStack Query mutation) |
| 담당 | Regina |
| Phase | Phase 1 — 프론트엔드 RCM 작업7 |
| 결정 출처 | claude.ai 사전 승인 (2026-06-11) |
| 예상 작업 시간 | 2~3시간 |
| 영향 파일 | `frontend/src/features/rcm/` 내 약 4~6개 파일 |
| 커밋 메시지 제안 | `feat(frontend): RCM 통제 추가/편집/단건 삭제 실 API 전환` |
| 브랜치 | `feature/fe-rcm-mutations` (ADR-0017 명명 규칙) |

---

## 사전 승인된 결정사항

| 항목 | 결정 |
|---|---|
| 작업 범위 | 통제 **추가 + 편집 + 단건 삭제** (3개 동시 전환) |
| 다건 선택 삭제 | 이번 작업 제외 — 다음 작업으로 |
| API 호출 방식 | TanStack Query `useMutation` |
| 삭제 UX | 행 끝 휴지통 아이콘 + 확인 Dialog |

---

## 작업 지시

`ClaudeICFR.md` (섹션 4.2 RCM 명세, 섹션 19 API 명세 표준),
`CLAUDE.md` (섹션 9 명세 동기화 체크),
`backend/app/api/rcm.py` 의 `POST /controls`, `PATCH /controls/{id}`, `DELETE /controls/{id}` 엔드포인트를 먼저 정확히 확인하고 아래를 구현해줘.

**작업 시작 전 필수 체크**:
1. `git fetch origin && git checkout main && git pull` 으로 최신 상태 확인
2. `feature/fe-rcm-mutations` 브랜치 생성
3. 백엔드 컨테이너 healthy 확인 (`docker-compose ps`)
4. 백엔드 응답·요청 스키마 정확히 매칭 (`backend/app/schemas/rcm.py` 의 ControlCreate, ControlUpdate)

---

## 1. 핵심 설계 원칙

- **mock 함수 완전 제거**: `useControls.ts`의 `addControl`, `updateControl`, `localOnlyControls` 모두 삭제
- **TanStack Query mutation 사용**: `useMutation` + `onSuccess`에서 `invalidateQueries`로 목록 자동 갱신
- **요청 페이로드 타입 분리**: `Control`(서버 응답)과 `ControlCreatePayload`/`ControlUpdatePayload`(클라이언트 → 서버) 구분
- **에러 처리**: 검증 오류(422), 중복(409 등) 시 사용자 친화 메시지로 표시
- **삭제는 확인 후 진행**: AlertDialog로 "정말 삭제할까요?" 확인 단계 필수
- **낙관적 업데이트는 사용 안 함**: 단순하게 mutation → invalidate 패턴

---

## 2. 생성/수정 파일 구조

```
frontend/src/features/rcm/
├── api/
│   ├── controlsApi.ts         ← 수정: createControl, updateControl, deleteControl 추가
│   ├── useControls.ts         ← 수정: addControl/updateControl mock 제거 + mutation 훅 추가
│   └── ... (기존 유지)
├── components/
│   ├── ControlFormDialog.tsx  ← 수정: mock 호출 → mutation 호출
│   ├── ControlTable.tsx       ← 수정: 행 끝 휴지통 아이콘 + onDelete 콜백
│   └── DeleteConfirmDialog.tsx ← 신규: 삭제 확인 AlertDialog
└── pages/
    └── RcmPage.tsx            ← 수정: 삭제 핸들러 + DeleteConfirmDialog 연결
```

필요 shadcn 컴포넌트: `alert-dialog`. 없으면 설치:
```bash
npx shadcn@latest add alert-dialog
```

---

## 3. 타입 정의 (types.ts 또는 controlsApi.ts)

백엔드 ControlCreate / ControlUpdate 스키마 확인 후 정확히 일치시킬 것.

```typescript
// 추가 요청 페이로드 — Control에서 id, created_at, updated_at 등 서버 생성 필드 제외
export type ControlCreatePayload = Omit<Control,
  | 'id'
  | 'created_at'
  | 'updated_at'
  | 'process_code'      // 서버에서 JOIN으로 채워주는 표시용 필드
  | 'sub_process_code'
  | 'risk_level'
>

// 편집 요청 페이로드 — 모든 필드가 옵셔널 (PATCH 의미상)
export type ControlUpdatePayload = Partial<ControlCreatePayload>
```

> 백엔드 스키마와 100% 매칭이 필수. `assertions`가 어떤 형태로 전달돼야 하는지(코드 배열인지 객체 배열인지) 백엔드 코드 확인.

---

## 4. controlsApi.ts 확장

기존 `fetchControls`에 더해 mutation 함수 3개 추가:

```typescript
import axiosInstance from '@/lib/axios'

export async function createControl(payload: ControlCreatePayload): Promise<Control> {
  const res = await axiosInstance.post<Control>('/api/rcm/controls', payload)
  return res.data
}

export async function updateControlById(
  id: string,
  payload: ControlUpdatePayload
): Promise<Control> {
  const res = await axiosInstance.patch<Control>(`/api/rcm/controls/${id}`, payload)
  return res.data
}

export async function deleteControl(id: string): Promise<void> {
  await axiosInstance.delete(`/api/rcm/controls/${id}`)
}
```

> 엔드포인트 경로는 백엔드 확인 후 정확히 매칭.

---

## 5. useControls.ts 수정

기존 `addControl`, `updateControl` mock 함수 **완전 제거**.

대신 mutation 훅 3개 노출:

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createControl, updateControlById, deleteControl } from './controlsApi'

export function useCreateControl() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createControl,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['controls'] })
    },
  })
}

export function useUpdateControl() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ControlUpdatePayload }) =>
      updateControlById(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['controls'] })
    },
  })
}

export function useDeleteControl() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteControl,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['controls'] })
    },
  })
}
```

---

## 6. ControlFormDialog.tsx 수정

기존 mock 호출 부분을 mutation 사용으로 교체:

```typescript
const createMutation = useCreateControl()
const updateMutation = useUpdateControl()

async function onSubmit(data: ControlFormData) {
  try {
    if (mode === 'create') {
      const saved = await createMutation.mutateAsync(data)
      toast.success('통제가 추가되었습니다')
      onSuccess?.(saved)
    } else if (mode === 'edit' && control) {
      const saved = await updateMutation.mutateAsync({
        id: control.id,
        payload: data,
      })
      toast.success('통제가 수정되었습니다')
      onSuccess?.(saved)
    }
    onOpenChange(false)
  } catch (err) {
    // 422 검증 오류면 어느 필드인지 표시, 그 외엔 일반 메시지
    const msg = extractErrorMessage(err)
    toast.error(msg)
  }
}
```

저장 버튼은 `createMutation.isPending || updateMutation.isPending` 동안 비활성화 + "저장 중..." 텍스트.

**중요**: `mockData.ts`와 `localOnlyControls` 사용 코드 제거 확인. 페이지 새로고침해도 데이터 유지되는 게 핵심 동작.

---

## 7. ControlTable.tsx 수정

각 행 끝에 **삭제 아이콘 추가**:

```
| 통제코드 | 통제명 | ... | 담당자 | [✏️] [🗑️] |
```

- lucide-react `Trash2` 아이콘 사용
- 호버 시 빨간색 강조 (`hover:bg-red-50 hover:text-red-600`)
- 클릭 시 `e.stopPropagation()` (행 클릭 = 상세보기와 분리)
- 부모로 `onDelete(control)` 콜백 전파

```typescript
interface ControlTableProps {
  // ... 기존
  onDelete?: (control: Control) => void
}
```

---

## 8. DeleteConfirmDialog.tsx (신규)

shadcn `AlertDialog` 사용. 삭제 확인 단계:

```
┌────────────────────────────────────────────┐
│ 통제 삭제 확인                              │
│                                             │
│ 정말 이 통제를 삭제하시겠습니까?            │
│                                             │
│ {control.code} — {control.name}             │
│                                             │
│ 이 작업은 되돌릴 수 없습니다.               │
├────────────────────────────────────────────┤
│              [취소]  [삭제]                 │
└────────────────────────────────────────────┘
```

**Props:**
```typescript
interface DeleteConfirmDialogProps {
  open: boolean
  control: Control | null
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  isPending: boolean    // 삭제 진행 중일 때 버튼 비활성화
}
```

- "삭제" 버튼은 빨간색 (`variant="destructive"`)
- `isPending` true일 때 "삭제 중..." 표시 + 두 버튼 모두 비활성화

---

## 9. RcmPage.tsx 수정

```typescript
const [deleteTarget, setDeleteTarget] = useState<Control | null>(null)
const deleteMutation = useDeleteControl()

function handleDeleteClick(control: Control) {
  setDeleteTarget(control)
}

async function handleDeleteConfirm() {
  if (!deleteTarget) return
  try {
    await deleteMutation.mutateAsync(deleteTarget.id)
    toast.success('통제가 삭제되었습니다')
    setDeleteTarget(null)
  } catch (err) {
    toast.error(extractErrorMessage(err))
  }
}

// JSX
<ControlTable ... onDelete={handleDeleteClick} />
<DeleteConfirmDialog
  open={deleteTarget !== null}
  control={deleteTarget}
  onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}
  onConfirm={handleDeleteConfirm}
  isPending={deleteMutation.isPending}
/>
```

---

## 10. mockData.ts 정리

- **파일 자체는 보존** (롤백 대비, 주석으로 "현재 사용 안 함, 롤백용" 표시)
- `useControls.ts`에서 mockData import 제거 확인
- `addControl`/`updateControl` 함수와 관련된 모든 코드 정리

---

## 11. ExcelUploadDialog 안내 문구 업데이트

이제 모든 게 실 API와 연결됐으므로 노란색 안내 박스 톤 조정:

**기존:**
> Excel 업로드는 실제 DB에 저장됩니다. 현재 통제 목록 화면은 mock 데이터를 표시 중이라 업로드된 항목이 바로 보이지 않을 수 있습니다.

**변경:**
> Excel 업로드는 실제 DB에 저장됩니다. 업로드 완료 후 통제 목록에 즉시 반영됩니다.

색상도 노란색(`bg-yellow-50`) → 파란색(`bg-blue-50`) 정보 톤으로 변경.

---

## 12. 완료 후 필수 작업

### 12.1 ClaudeICFR.md 업데이트
- **섹션 12.2**: RCM FE 컬럼 → "목록·검색·필터·페이지네이션·추가·편집·삭제·Excel 업로드 모두 실 API 연결"
- **섹션 14**: "Regina: RCM 추가/편집/단건 삭제 실 API 전환 — mock 완전 제거" 한 줄
- **섹션 18.2**: 일일 진행 로그 (2026-06-11)

### 12.2 git 작업

```bash
git checkout -b feature/fe-rcm-mutations
# (작업 수행)
git add frontend/ ClaudeICFR.md prompts/ICFR_frontend_9_20260611.md
git commit -m "feat(frontend): RCM 통제 추가/편집/단건 삭제 실 API 전환"
git push -u origin feature/fe-rcm-mutations
```

> 커밋 메시지는 한 줄 단순 형식 (Windows PowerShell heredoc 회피).

### 12.3 동작 확인 체크리스트
- [ ] `npm run build` 통과
- [ ] 통제 추가 → 새로고침해도 유지 (DB 영구 저장)
- [ ] 통제 편집 → 변경사항 새로고침 후에도 유지
- [ ] 행 끝 휴지통 아이콘 클릭 → 확인 Dialog 표시
- [ ] 확인 클릭 → 삭제 + 토스트 + 목록 즉시 갱신
- [ ] 취소 클릭 → 삭제 안 됨
- [ ] 잘못된 데이터 입력 시 422 에러 사용자에게 표시
- [ ] 백엔드 끄고 시도 시 명확한 에러 메시지
- [ ] Excel 업로드 안내 문구 톤 업데이트 확인

---

## 13. 작업 외 (다음 작업으로 미룸)

- 다건 선택 삭제 (`POST /controls/bulk-delete` — 체크박스 + 한 번에 삭제)
- 다건 일괄 편집 (`POST /controls/bulk-update`)
- 위험 매트릭스 시각화 (`GET /matrix`)
- 통제 변경 이력 표시

---

## 14. 참조

- 백엔드 통제 CRUD: `backend/app/api/rcm.py` (POST/PATCH/DELETE /controls)
- 백엔드 스키마: `backend/app/schemas/rcm.py` (ControlCreate, ControlUpdate)
- 협업 분담: ADR-0017
- 이전 작업: `prompts/ICFR_frontend_7_20260601.md` (useControls API 전환)
- 다음 작업: `ICFR_frontend_10` (다건 선택 + bulk 작업 또는 다른 모듈)
