# ICFR_frontend_4_20260522.md — Phase 1: RCM 통제 상세보기 슬라이드 패널 (mock 데이터)

## 메타 정보

| 항목 | 값 |
|---|---|
| 작업 일시 | 2026-05-22 |
| 작업 유형 | RCM 통제 상세보기 슬라이드 패널 (Sheet) + 편집 버튼 자리 |
| 담당 | Regina |
| Phase | Phase 1 — 프론트엔드 RCM 작업2 |
| 결정 출처 | claude.ai 사전 승인 (2026-05-22) |
| 예상 작업 시간 | 1~1.5시간 |
| 영향 파일 | `frontend/src/features/rcm/` 내 신규 약 2~3개 + ControlTable·RcmPage 수정 |
| 커밋 메시지 제안 | `feat(frontend): RCM 통제 상세보기 슬라이드 패널 (mock 데이터)` |
| 브랜치 | `feature/fe-rcm-detail` (ADR-0017 명명 규칙) |

---

## 사전 승인된 결정사항

| 항목 | 결정 |
|---|---|
| 상세 표시 방식 | 오른쪽에서 슬라이드로 열리는 패널 (shadcn/ui `Sheet`) — 목록 유지한 채 |
| 편집 기능 | 이번엔 보기 전용. 패널 우상단에 "편집" 버튼 자리만 마련 (클릭 시 "준비중" 토스트 또는 비활성) |
| 데이터 방식 | mock (기존 useControls 데이터 재사용, 신규 API 호출 없음) |

---

## 작업 지시

`ClaudeICFR.md` (섹션 4.2 RCM 명세, 섹션 14 변경 로그, ADR-0017),
`CLAUDE.md` (섹션 9 명세 동기화 체크)를 먼저 확인하고, 아래 통제 상세보기 슬라이드 패널을 구현해줘.

**작업 시작 전 필수 체크 (CLAUDE.md 섹션 9)**:
1. `git fetch origin && git checkout main && git pull` 으로 최신 상태 확인
2. **주의**: 직전 작업 브랜치 `feature/fe-rcm-list`가 아직 main에 머지 안 됐을 수 있음. 머지 여부 확인 후, 미머지 상태면 `feature/fe-rcm-list`에서 분기하거나 협업자와 머지 협의. (이전 작업의 RCM 목록 코드가 있어야 이번 작업 가능)
3. `feature/fe-rcm-detail` 브랜치 생성
4. 기존 `frontend/` 빌드 정상 동작 확인 (`npm run build`)

---

## 1. 핵심 설계 원칙

- 기존 `useControls` 훅이 반환한 통제 데이터를 그대로 재사용 (신규 데이터 fetch 없음)
- 목록에서 통제 코드(또는 행) 클릭 → 해당 통제 객체를 패널에 전달
- 패널은 보기 전용. 편집 버튼은 자리만 (다음 작업에서 편집 폼 연결)
- 나중에 실제 API 연동 시: 상세는 `GET /api/rcm/controls/{id}` 호출로 교체 가능하나, 지금은 목록 데이터로 충분

---

## 2. 생성/수정 파일 구조

```
frontend/src/features/rcm/
├── components/
│   ├── ControlDetailSheet.tsx    ← 신규: 상세 슬라이드 패널
│   └── ControlTable.tsx          ← 수정: 행/코드 클릭 시 onSelect 콜백 추가
└── pages/
    └── RcmPage.tsx               ← 수정: 선택된 통제 state + Sheet 연결
```

shadcn/ui `Sheet`, `Separator` 컴포넌트 필요. 없으면 설치:
```bash
npx shadcn@latest add sheet separator
```

---

## 3. 통제 상세 패널 (components/ControlDetailSheet.tsx)

shadcn/ui `Sheet` 사용. 오른쪽에서 슬라이드로 열림 (`side="right"`). 너비는 넓게 (`sm:max-w-xl` 정도, 약 576px).

**Props:**
```typescript
interface ControlDetailSheetProps {
  control: Control | null    // null이면 닫힌 상태
  open: boolean
  onOpenChange: (open: boolean) => void
}
```

**패널 내부 구성 (위 → 아래 순서):**

### 3.1 헤더 영역
- 통제 코드 (`code`) — 큰 글씨, 굵게
- 통제명 (`name`) — 그 아래
- 우상단: **"편집" 버튼** (자리만 — `variant="outline"`, 클릭 시 비활성 또는 "준비중입니다" 안내. 실제 편집은 다음 작업)
- 핵심통제면 ★핵심 Badge 표시

### 3.2 기본 정보 섹션
`Separator`로 구분. 라벨-값 2열 형태로 표시:

| 라벨 | 값 |
|---|---|
| 프로세스 | process_code |
| 세부 프로세스 | sub_process_code |
| 위험 수준 | risk_level (색상 Badge, 목록과 동일 매핑) |
| 통제 목적 | objective |
| 담당자 | owner_name |

### 3.3 통제 분류 섹션
`Separator`로 구분:

| 라벨 | 값 |
|---|---|
| 예방/적발 | preventive_detective (라벨) |
| 자동/수동 | auto_manual (라벨) |
| 수행 주기 | frequency (라벨) |
| IPE 관련성 | ipe_relevant |
| 핵심통제 | is_key_control (예/아니오) |

### 3.4 통제 활동 유형 섹션
6종 활동 bool을 체크 표시로. true인 것만 강조하거나, 전체를 보여주되 true는 체크 아이콘:

- 승인 (activity_approval)
- 검증 (activity_verification)
- 실사 (activity_inspection)
- 마스터 (activity_master)
- 조정 (activity_reconciliation)
- 감독 (activity_supervision)

true는 `CheckCircle2` 아이콘(초록), false는 흐린 빈 동그라미.

### 3.5 어서션 섹션
- 연결된 어서션(`assertions[]`)을 Badge로 나열
- 각 Badge에 코드 + 한글 라벨 (예: "E 실재성") — `ASSERTION_LABELS` 활용

### 3.6 관련 정보 섹션
`Separator`로 구분. 값이 있을 때만 표시:

| 라벨 | 값 |
|---|---|
| 관련 계정 | related_accounts |
| 관련 시스템 | related_systems |
| EUC 설명 | euc_description |
| 통제 설명 | description |

값이 null이면 "—" 또는 "정보 없음" 표시.

---

## 4. ControlTable.tsx 수정

- `onSelect?: (control: Control) => void` prop 추가
- 통제 코드 셀(또는 행 전체)에 클릭 핸들러 연결 → `onSelect(control)` 호출
- 통제 코드는 클릭 가능함을 나타내는 스타일 (파란색 + hover 밑줄 또는 커서 포인터)

---

## 5. RcmPage.tsx 수정

```tsx
const [selectedControl, setSelectedControl] = useState<Control | null>(null)
const [sheetOpen, setSheetOpen] = useState(false)

function handleSelect(control: Control) {
  setSelectedControl(control)
  setSheetOpen(true)
}

// ControlTable에 onSelect={handleSelect} 전달
// 하단에 <ControlDetailSheet control={selectedControl} open={sheetOpen} onOpenChange={setSheetOpen} />
```

---

## 6. 완료 후 필수 작업

### 6.1 ClaudeICFR.md 업데이트
- **섹션 12.2**: RCM 모듈 FE 비고에 "목록+검색+상세보기" 표시
- **섹션 14**: 변경 로그에 "Regina: Phase 1 RCM 통제 상세보기 슬라이드 패널 (mock) 완료" 한 줄 추가
- **섹션 18.2**: 일일 진행 로그 추가 (2026-05-22)

### 6.2 git 작업 (커밋 전 사용자 OK 확인 필수)

```bash
git checkout -b feature/fe-rcm-detail
# (작업 수행)
git add frontend/ ClaudeICFR.md prompts/ICFR_frontend_4_20260522.md
git commit -m "feat(frontend): RCM 통제 상세보기 슬라이드 패널 (mock 데이터)"
git push -u origin feature/fe-rcm-detail
```

### 6.3 동작 확인 체크리스트
- [ ] `npm run build` 통과 (TypeScript 오류 없음)
- [ ] `npm run dev` → RCM 목록에서 통제 코드 클릭 → 오른쪽 패널 슬라이드로 열림
- [ ] 패널에 코드·통제명·분류·활동·어서션·관련정보 모두 표시
- [ ] 위험수준 Badge 색상이 목록과 동일하게 표시
- [ ] 통제 활동 유형: true는 초록 체크, false는 흐린 표시
- [ ] 어서션 Badge에 코드+한글 라벨 표시
- [ ] 관련 정보 값이 없으면 "—" 표시
- [ ] "편집" 버튼이 우상단에 보임 (클릭 시 "준비중" 또는 비활성)
- [ ] 패널 바깥 클릭 또는 X 버튼 → 패널 닫힘, 목록 유지
- [ ] 다른 통제 클릭 → 패널 내용이 그 통제로 갱신됨

---

## 7. 작업 외 (다음 작업으로 미룸)

- 통제 추가/편집 폼 (편집 버튼 실제 연결 — 다음 작업)
- Excel 업로드 (preview → commit)
- 위험 매트릭스 시각화
- 실제 API 연동 (`GET /controls/{id}`)
- 다건 선택 + bulk 작업

---

## 8. 참조

- RCM 모듈 명세: `ClaudeICFR.md` 섹션 4.2
- 백엔드 RCM API: `backend/app/api/rcm.py` (상세는 `GET /controls/{id}`, 이번엔 미사용)
- 협업 분담: ADR-0017
- 이전 작업: `prompts/ICFR_frontend_3_20260522.md` (RCM 목록 + 검색/필터)
- 다음 작업: `ICFR_frontend_5` (통제 추가/편집 폼)
