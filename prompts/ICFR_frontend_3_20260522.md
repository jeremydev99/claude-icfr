# ICFR_frontend_3_20260522.md — Phase 1: RCM 통제 목록 + 검색/필터 화면 (mock 데이터)

## 메타 정보

| 항목 | 값 |
|---|---|
| 작업 일시 | 2026-05-22 |
| 작업 유형 | RCM 통제 목록 테이블 + 검색/필터 UI (mock 데이터 기반) |
| 담당 | Regina |
| Phase | Phase 1 — 프론트엔드 RCM 작업1 |
| 결정 출처 | claude.ai 사전 승인 (2026-05-22) |
| 예상 작업 시간 | 1.5~2시간 |
| 영향 파일 | `frontend/src/features/rcm/` 내 신규 약 8~10개 파일 |
| 커밋 메시지 제안 | `feat(frontend): RCM 통제 목록 + 검색/필터 화면 (mock 데이터)` |
| 브랜치 | `feature/fe-rcm-list` (ADR-0017 명명 규칙) |

---

## 사전 승인된 결정사항

| 항목 | 결정 |
|---|---|
| 이번 작업 범위 | 통제 목록 테이블 + 검색/필터 (메인 화면만) |
| 데이터 방식 | mock 데이터 (백엔드 API 미연결, 나중에 교체 쉽도록 분리) |
| 제외 범위 | 상세보기, 편집, Excel 업로드, 매트릭스 (다음 작업) |

---

## 작업 지시

`ClaudeICFR.md` (섹션 4.2 RCM 명세, 섹션 14 변경 로그, ADR-0017·0018·0020),
`CLAUDE.md` (섹션 9 명세 동기화 체크)를 먼저 확인하고, 아래 RCM 통제 목록 화면을 mock 데이터 기반으로 구현해줘.

**작업 시작 전 필수 체크 (CLAUDE.md 섹션 9)**:
1. `git fetch origin && git checkout main && git pull` 으로 최신 상태 확인
2. `feature/fe-rcm-list` 브랜치 새로 생성
3. 기존 `frontend/` 빌드 정상 동작 확인 (`npm run build`)
4. 백엔드 RCM 스키마 참조: `backend/app/schemas/rcm.py` 및 `backend/app/api/rcm.py`의 Control 필드·검색 파라미터 (mock 타입을 실제 API 응답과 일치시키기 위함)

---

## 1. 핵심 설계 원칙

**나중에 진짜 API로 쉽게 교체할 수 있도록 데이터 계층을 분리한다.**

- mock 데이터는 `features/rcm/api/mockData.ts` 한 곳에만 둔다
- 화면 컴포넌트는 데이터가 mock인지 실제 API인지 몰라야 한다 (`useControls` 훅을 통해서만 접근)
- 나중에 `useControls` 훅 내부만 axios 호출로 바꾸면 화면 수정 없이 실제 API 연동 완료
- 타입 정의(`types.ts`)는 백엔드 스키마와 100% 일치시킨다

---

## 2. 생성 파일 구조

```
frontend/src/features/rcm/
├── types.ts                      ← Control, 검색 파라미터 타입 (백엔드 스키마 일치)
├── api/
│   ├── mockData.ts               ← mock 통제 데이터 30건
│   └── useControls.ts            ← 데이터 조회 훅 (지금은 mock, 나중에 axios로 교체)
├── components/
│   ├── ControlTable.tsx          ← 통제 목록 테이블
│   ├── ControlSearchBar.tsx      ← 텍스트 검색 + 필터 영역
│   └── ControlFilterChips.tsx    ← 적용된 필터 표시 칩
└── pages/
    └── RcmPage.tsx               ← 기존 placeholder 교체 (목록 화면으로)
```

---

## 3. 타입 정의 (types.ts)

백엔드 `Control` 스키마와 일치시킬 것. 주요 필드:

```typescript
// 어서션 코드 (RiskCategory)
export type AssertionCode = 'E' | 'C' | 'R' | 'V' | 'P' | 'O' | 'M'

// 위험 수준
export type RiskLevel = 'LR' | 'MR' | 'HR' | 'SR'

// 수행 주기
export type Frequency = 'O' | 'D' | 'W' | 'M' | 'Q' | 'A'

// 예방/적발
export type PreventiveDetective = 'P' | 'D'

// 자동/수동/IT
export type AutoManual = 'A' | 'M' | 'IT'

export interface Control {
  id: string                       // UUID
  code: string                     // 예: O2C-AR-C001
  name: string
  description: string | null
  objective: string | null
  owner_name: string | null
  risk_id: string                  // UUID
  // 분류
  is_key_control: boolean
  preventive_detective: PreventiveDetective
  auto_manual: AutoManual
  frequency: Frequency
  ipe_relevant: 'Y' | 'N' | 'N/A'
  // 활동 유형 (6종 bool)
  activity_approval: boolean
  activity_verification: boolean
  activity_inspection: boolean
  activity_master: boolean
  activity_reconciliation: boolean
  activity_supervision: boolean
  // 관련 정보
  related_accounts: string | null
  related_systems: string | null
  euc_description: string | null
  // 연결된 어서션 (표시용)
  assertions: AssertionCode[]
  // 상위 계층 (표시용 - 검색 결과에 포함)
  process_code: string
  sub_process_code: string
  risk_level: RiskLevel
  created_at: string
}

// 검색 파라미터 (백엔드 GET /controls/search 와 일치)
export interface ControlSearchParams {
  q?: string
  process_code?: string
  sub_process_code?: string
  risk_level?: RiskLevel
  frequency?: Frequency
  is_key_control?: boolean
  auto_manual?: AutoManual
  preventive_detective?: PreventiveDetective
  assertion?: AssertionCode
  owner?: string
  skip?: number
  limit?: number
  sort_by?: 'code' | 'name' | 'frequency' | 'created_at'
  sort_order?: 'asc' | 'desc'
}

// 목록 응답 (백엔드 공통 형태)
export interface ControlListResponse {
  items: Control[]
  total: number
  skip: number
  limit: number
}
```

라벨 매핑(한글 표시)용 상수도 함께 정의:
- `RISK_LEVEL_LABELS`: LR→"낮음", MR→"보통", HR→"높음", SR→"유의"
- `FREQUENCY_LABELS`: O→"수시", D→"일", W→"주", M→"월", Q→"분기", A→"연"
- `AUTO_MANUAL_LABELS`: A→"자동", M→"수동", IT→"IT의존수동"
- `PD_LABELS`: P→"예방", D→"적발"
- `ASSERTION_LABELS`: E→"실재성", C→"완전성", R→"권리와의무", V→"평가", P→"표시와공시", O→"발생", M→"기타"

---

## 4. mock 데이터 (api/mockData.ts)

- `Control` 타입에 맞는 **30건** 생성
- 백엔드 시드(Acme Corp)와 유사한 형태: 프로세스 O2C/P2P/R2R/HR/ITG 분포
- 통제 코드는 `{서브프로세스}-C{3자리}` 형식 (예: O2C-AR-C001)
- 다양성 확보: is_key_control 절반 정도 true, frequency·auto_manual·risk_level 골고루 분포
- 어서션은 각 통제마다 1~3개 랜덤 배정
- owner_name은 한국 이름 샘플 (김재무, 이회계, 박영업 등)

---

## 5. 데이터 조회 훅 (api/useControls.ts)

**이 파일이 mock ↔ 실제 API 교체 지점이다.**

```typescript
import { useState, useMemo } from 'react'
import { mockControls } from './mockData'
import type { Control, ControlSearchParams, ControlListResponse } from '../types'

// 지금은 mock 데이터를 클라이언트에서 필터링.
// 나중에 이 함수 내부만 axios.get('/api/rcm/controls/search', { params }) 로 교체.
export function useControls(params: ControlSearchParams): {
  data: ControlListResponse
  isLoading: boolean
} {
  // mock 구현: 클라이언트 사이드 필터 + 정렬 + 페이지네이션
  const data = useMemo(() => {
    let filtered = [...mockControls]
    // q: code/name/owner_name 부분 일치
    // process_code, risk_level, frequency, is_key_control 등 각 필터 적용
    // sort_by + sort_order 정렬
    // skip + limit 페이지네이션
    // → { items, total, skip, limit } 반환
    return filteredResult
  }, [params])

  return { data, isLoading: false }
}
```

> 주석으로 "실제 API 교체 위치"를 명확히 표시할 것. (TODO: replace with axios)

---

## 6. 통제 목록 테이블 (components/ControlTable.tsx)

shadcn/ui `Table` 컴포넌트 사용. 필요 시 `npx shadcn@latest add table badge` 실행.

**표시 컬럼:**

| 컬럼 | 내용 | 비고 |
|---|---|---|
| 통제코드 | code | 클릭 가능 스타일(나중에 상세 연결), 정렬 가능 |
| 통제명 | name | 정렬 가능 |
| 프로세스 | process_code | |
| 위험수준 | risk_level | Badge 색상: SR=빨강, HR=주황, MR=노랑, LR=초록 |
| 핵심통제 | is_key_control | true면 ★ 또는 "핵심" Badge |
| 예방/적발 | preventive_detective | 라벨 표시 |
| 자동/수동 | auto_manual | 라벨 표시 |
| 주기 | frequency | 라벨 표시 |
| 어서션 | assertions[] | 작은 Badge 여러 개 (E, C, ...) |
| 담당자 | owner_name | |

**기능:**
- 컬럼 헤더 클릭 → 정렬 토글 (code/name/frequency)
- 행 hover 시 배경 강조
- 데이터 없을 때: "검색 결과가 없습니다" 빈 상태 표시
- 페이지네이션: 하단에 이전/다음 + "전체 N건 중 X-Y" 표시 (limit 기본 20)

---

## 7. 검색/필터 영역 (components/ControlSearchBar.tsx)

상단에 배치. 레이아웃:

```
┌──────────────────────────────────────────────────────────┐
│ [🔍 통제코드·통제명·담당자 검색...        ]  [필터 ▼]    │
│                                                            │
│ (필터 펼침 시)                                            │
│ 프로세스: [전체▼]  위험수준: [전체▼]  주기: [전체▼]      │
│ 자동/수동: [전체▼]  예방/적발: [전체▼]  어서션: [전체▼]  │
│ □ 핵심통제만 보기                          [초기화]       │
└──────────────────────────────────────────────────────────┘
```

- 텍스트 검색: 입력 시 디바운스(300ms) 후 `q` 파라미터 갱신
- 드롭다운 필터: shadcn/ui `Select` 사용 (필요 시 `npx shadcn@latest add select`)
- "핵심통제만 보기": shadcn/ui `Checkbox`
- "초기화" 버튼: 모든 필터 리셋
- 필터 영역은 접기/펼치기 가능 (기본 접힘, "필터" 버튼으로 토글)

---

## 8. 적용된 필터 칩 (components/ControlFilterChips.tsx)

- 현재 적용된 필터를 칩(Badge) 형태로 검색바 아래 표시
- 예: `프로세스: O2C ✕`  `위험수준: 높음 ✕`  `핵심통제 ✕`
- 각 칩의 ✕ 클릭 → 해당 필터만 제거
- 적용된 필터 없으면 칩 영역 숨김

---

## 9. RcmPage.tsx (기존 placeholder 교체)

```
┌─────────────────────────────────────────────┐
│ RCM 관리                                     │  ← 페이지 제목
│ 리스크-통제 매트릭스 관리                    │  ← 설명
│                                              │
│ [ControlSearchBar]                           │
│ [ControlFilterChips]                         │
│ [ControlTable]                               │
└─────────────────────────────────────────────┘
```

- 검색 파라미터는 `RcmPage`에서 `useState`로 관리하고 하위 컴포넌트에 props로 전달
- `useControls(params)` 호출해서 결과를 `ControlTable`에 전달

---

## 10. 완료 후 필수 작업

### 10.1 ClaudeICFR.md 업데이트
- **섹션 12.2**: RCM 모듈 FE 컬럼 → `🔄 진행중` (목록 화면 완료, 상세·편집 남음 비고 표시)
- **섹션 14**: 변경 로그에 "Regina: Phase 1 RCM 통제 목록 + 검색/필터 화면 (mock) 완료" 한 줄 추가
- **섹션 18.2**: 일일 진행 로그 추가 (2026-05-22)

### 10.2 git 작업 (커밋 전 사용자 OK 확인 필수)

```bash
git checkout -b feature/fe-rcm-list
# (작업 수행)
git add frontend/ ClaudeICFR.md prompts/ICFR_frontend_3_20260522.md
git commit -m "feat(frontend): RCM 통제 목록 + 검색/필터 화면 (mock 데이터)"
git push -u origin feature/fe-rcm-list
```

### 10.3 동작 확인 체크리스트
- [ ] `npm run build` 통과 (TypeScript 오류 없음)
- [ ] `npm run dev` → 로그인 후 좌측 메뉴 "RCM 관리" 클릭 → 목록 화면 표시
- [ ] mock 통제 30건이 테이블에 표시됨
- [ ] 텍스트 검색 입력 → 결과 필터링 동작
- [ ] 프로세스/위험수준/주기 등 드롭다운 필터 동작
- [ ] "핵심통제만 보기" 체크 → 필터링 동작
- [ ] 적용된 필터가 칩으로 표시되고, ✕ 클릭 시 제거됨
- [ ] 컬럼 헤더 클릭 → 정렬 동작
- [ ] 페이지네이션 이전/다음 동작
- [ ] 위험수준 Badge 색상이 수준별로 다르게 표시됨
- [ ] 검색 결과 0건일 때 빈 상태 메시지 표시

---

## 11. 작업 외 (다음 작업으로 미룸)

- 통제 상세보기 모달/페이지 (다음: `ICFR_frontend_4`)
- 통제 추가/편집 폼
- Excel 업로드 (preview → commit 2단계 UI)
- 위험 매트릭스 시각화 뷰
- 실제 백엔드 API 연동 (useControls 훅 내부 교체)
- 다건 선택 + bulk 작업

---

## 12. 참조

- RCM 모듈 명세: `ClaudeICFR.md` 섹션 4.2
- 백엔드 RCM API: `backend/app/api/rcm.py`, `backend/app/schemas/rcm.py`
- 검색 파라미터 출처: `GET /api/rcm/controls/search`
- 협업 분담: ADR-0017
- PK 정책: ADR-0020 (UUID v7)
- 이전 작업: `prompts/ICFR_frontend_2_20260521.md` (작업5 모듈 골조)
- 다음 작업: `ICFR_frontend_4` (RCM 통제 상세보기)
