# RAWC(위험평가) 화면 — RCM 통제 상세 패널 내 섹션 추가

## 목표
ControlDetailSheet 안에 "위험평가(RAWC)" 섹션을 추가한다.
7개 항목(1~3점) 평가, 전기효과성, 종합평가, 평가자/평가일 입력 및 표시.
회계연도(fiscal_year) 기준으로 평가 1건을 조회·생성·수정한다.

## 사전 확인 (읽기만, 수정 금지)
- `frontend/src/features/rcm/components/ControlDetailSheet.tsx` (섹션 추가 위치 파악)
- `frontend/src/features/rcm/types.ts`
- `frontend/src/features/test/types.ts` (패턴 참고용, RAWC 관련 타입 없으면 신규로 둘 폴더에 둘지 결정)
- `frontend/src/features/test/api/testRunsApi.ts`, `useTestRuns.ts` (axios 패턴 참고)

## API 스펙 (확정)
| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | /api/test/rawc/by-control/{control_id}?fiscal_year= | - | { items: ControlRiskAssessmentRead[], total } |
| GET | /api/test/rawc?control_id=&fiscal_year=&skip=&limit= | - | { items, total, skip, limit } |
| POST | /api/test/rawc | ControlRiskAssessmentCreate | ControlRiskAssessmentRead (201) |
| GET | /api/test/rawc/{rawc_id} | - | ControlRiskAssessmentRead |
| PATCH | /api/test/rawc/{rawc_id} | ControlRiskAssessmentUpdate | ControlRiskAssessmentRead |
| DELETE | /api/test/rawc/{rawc_id} | - | 204 |

### ControlRiskAssessment 필드
```ts
interface ControlRiskAssessment {
  id: string
  control_id: string
  fiscal_year: number
  frequency_score: number      // 1-3
  nature_score: number         // 1-3
  precision_score: number      // 1-3
  dependency_score: number     // 1-3
  automation_score: number     // 1-3
  authority_score: number      // 1-3
  review_score: number         // 1-3
  prior_year_effectiveness: 'Effective' | 'Not_Effective' | 'N/A'
  overall_assessment: 'Not_Higher' | 'Higher'
  assessor_id: string | null
  assessment_date: string | null  // date
  created_at: string
  updated_at: string
}
```

각 점수 필드 기본값은 2. Create 시 control_id, fiscal_year 필수, 나머지는 기본값 사용 가능.

## 작업 순서

### 1. 브랜치 생성
```powershell
git checkout main
git pull origin main
git checkout -b feature/fe-rawc-section
```

### 2. types.ts 추가
파일: `frontend/src/features/rcm/types.ts`

위 ControlRiskAssessment 인터페이스 + Create/Update payload 타입 추가.
점수 항목 7개를 배열로 묶은 상수도 추가 (라벨 매핑용):
```ts
export const RAWC_SCORE_FIELDS = [
  { key: 'frequency_score', label: '빈도' },
  { key: 'nature_score', label: '성격' },
  { key: 'precision_score', label: '정밀도' },
  { key: 'dependency_score', label: '의존성' },
  { key: 'automation_score', label: '자동화' },
  { key: 'authority_score', label: '권한' },
  { key: 'review_score', label: '검토' },
] as const
```

### 3. rawcApi.ts 신규 생성
파일: `frontend/src/features/rcm/api/rawcApi.ts`

- `fetchRawcByControl(controlId, fiscalYear?)` → GET /api/test/rawc/by-control/{control_id}
- `createRawc(payload)` → POST /api/test/rawc
- `updateRawc(id, payload)` → PATCH /api/test/rawc/{id}

### 4. useRawc.ts 신규 생성
파일: `frontend/src/features/rcm/api/useRawc.ts`

- `useRawcByControl(controlId, fiscalYear)` — useQuery, enabled: !!controlId
- `useCreateRawc()` — useMutation, 성공 시 관련 쿼리 invalidate
- `useUpdateRawc()` — useMutation, 성공 시 관련 쿼리 invalidate

### 5. RawcSection.tsx 신규 생성
파일: `frontend/src/features/rcm/components/RawcSection.tsx`

```ts
interface Props {
  controlId: string
  fiscalYear: number
}
```

구성:
- 해당 control_id + fiscal_year로 기존 RAWC 평가 조회
- **평가 없으면**: "위험평가 입력" 버튼 → 클릭 시 입력 폼 표시 (기본값 2점)
- **평가 있으면**: 읽기 모드로 표시 + "편집" 버튼

**입력/편집 폼:**
- 7개 점수 항목: RAWC_SCORE_FIELDS 매핑, 각각 1~3 select 또는 segmented button
- 전기효과성: select (Effective/Not_Effective/N/A → 한국어 라벨 매핑)
- 종합평가: select (Not_Higher/Higher → 한국어 라벨 매핑)
- 평가자/평가일: 표시만 (assessor_id는 현재 로그인 사용자로 자동 설정, assessment_date는 오늘 날짜 자동 설정 — 수동 입력 받지 않음)
- 저장 버튼 → 신규면 useCreateRawc, 기존 있으면 useUpdateRawc

### 6. ControlDetailSheet.tsx 수정
파일: `frontend/src/features/rcm/components/ControlDetailSheet.tsx`

- 기존 5개 섹션 아래에 "위험평가(RAWC)" 섹션 추가
- `<RawcSection controlId={control.id} fiscalYear={현재 회계연도} />` 렌더링
- 회계연도는 RcmPage에서 쓰는 현재 선택된 연도 값을 그대로 props로 내려받아 사용 (이미 있는 fiscal_year 상태 재사용, 신규 상태 추가 금지)

## 완료 조건
- 통제 상세 패널에 위험평가 섹션 표시
- 평가 없을 때 입력 폼, 있을 때 읽기 모드 정상 전환
- 점수 입력 1~3 범위로 제한
- 저장 시 실 API 반영 확인
- TypeScript 오류 없음
- 빌드 통과

### 7. 커밋 & push
```powershell
git add frontend/src/features/rcm/
git commit -m "feat(frontend): RCM 통제 상세에 RAWC 위험평가 섹션 추가"
git push -u origin feature/fe-rawc-section
```

### 8. 화면 테스트 후 main 머지
화면 테스트 OK 확인 후:
```powershell
git checkout main
git merge --no-ff feature/fe-rawc-section
git push origin main
```
