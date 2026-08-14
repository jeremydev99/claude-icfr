# ICFR-PROMPT-2A3-2-mutation-ui-wiring

## 목적
통제(control) 단위 mutation(생성/수정/삭제) 잠금을 해제해 실제 API 왕복이 동작하게 배선한다. mutation 훅·다이얼로그·핸들러는 이미 완성돼 있고, 막고 있는 것은 버튼들의 `disabled={RCM_MUTATION_LOCKED}`뿐이다. 이번 작업은 **(a) mutation 잠금 물리 제거, (b) Excel 업로드 잠금 분리(rename), (c) 삭제 다이얼로그 source 분기 문구, (d) baseline 편집 안내 힌트(선택)** 를 수행한다. 새 훅·새 컴포넌트는 만들지 않는다.

## 배경 (확정된 사실)
- 백엔드 계약(코드 근거 확정, ClaudeICFR.md 13.4 항목6 / api/rcm.py:404-522):
  - PATCH `/controls/{id}`: 서버가 baseline 값과 자동 diff해서 override instance 생성/해제. **FE는 baseline이든 tenant-add든 폼을 통째로 열어 그대로 PATCH. 필드 단위 잠금·분기 불필요.**
  - DELETE `/controls/{id}`: 단일 엔드포인트. 서버가 baseline이면 exclude, tenant-add면 soft delete로 분기. FE는 source별 다른 호출 안 함.
  - envelope flat(source/baseline_id/is_overridden), resolver가 action->is_overridden 매핑 서버 완료.
- 협업자가 mutation 잠금 걷어도 된다고 명시(백엔드 mutation 준비 완료).
- 현재 코드 상태(사전 확인 완료):
  - `useCreateControl`/`useUpdateControl`/`useDeleteControl`(useControls.ts) 이미 존재.
  - `RcmPage.tsx`가 생성/편집/삭제 상태·핸들러·다이얼로그(ControlFormDialog/DeleteConfirmDialog) 렌더링까지 전부 연결 완료.
  - 막고 있는 건 버튼 disabled 삼항뿐.
  - `Control.envelope` required 전환 완료(2-A-3-1) — 다이얼로그 control prop에 envelope 존재.
  - `resolveDeleteSemantics`/`isBaseline` 은 `sourceEnvelope.ts` 정의됨(resolveDeleteSemantics가 내부적으로 isBaseline 사용).

## 작업 범위

### (a) mutation 잠금 물리 제거 — 상수 flip 아님, 참조 제거
- 다음 4곳의 `disabled={RCM_MUTATION_LOCKED}` / `title` 삼항을 **물리 제거**:
  - `ControlTable.tsx` "+통제 추가"(112-113), 행 편집(234-235), 행 삭제(244-245)
  - `ControlDetailSheet.tsx` 편집(91-92)
- 처리:
  - `disabled` 속성에 LOCK 외 다른 조건(예: isPending)이 함께 걸려 있으면 **그 조건은 보존**하고 LOCK 조건만 제거. LOCK 단독이면 disabled 속성 자체 삭제.
  - `title`이 LOCK 삼항이면 잠금 없는 고정 문자열로 정리(또는 잠금 안내 전용이었으면 제거).
  - 죽은 조건분기가 남지 않게 정리.

### (b) Excel 업로드 잠금 분리 — rename (RCM_MUTATION_LOCKED -> EXCEL_UPLOAD_LOCKED)
- Excel 업로드 버튼(`ControlTable.tsx:103-104`)은 13.6 버그(다중 헤더행 미대응으로 0건 파싱)가 미해소이므로 **잠금 유지**.
- 단, mutation 잠금과 이름·의미가 어긋나지 않게 상수를 실제 의미로 rename:
  - `rcmMutationLock.ts`의 `RCM_MUTATION_LOCKED` -> `EXCEL_UPLOAD_LOCKED`로 이름 변경(값 true 유지).
  - 파일 상단 주석을 "Excel 업로드 전용 잠금 — 13.6 다중 헤더행 파싱 버그 해소 시까지 유지"로 갱신. 파일명도 의미에 맞게 정리 가능(예: excelUploadLock.ts) — 파일명 변경 시 import 경로도 함께 수정.
  - Excel 업로드 버튼의 `disabled`/`title`이 이 새 상수(EXCEL_UPLOAD_LOCKED)를 참조하도록 유지.
- 결과: mutation 4곳은 잠금 제거, Excel 1곳만 EXCEL_UPLOAD_LOCKED로 명시적 잠금. `RCM_MUTATION_LOCKED`라는 이름은 코드베이스에서 사라짐(오해 소지 제거).

### (c) 삭제 다이얼로그 source 분기 문구
- `DeleteConfirmDialog.tsx`는 현재 하드코딩("통제 삭제 확인" / "선택한 통제를 삭제합니다.") — source 분기 없음.
- **새 prop 추가 없이 내부에서** `resolveDeleteSemantics(control?.envelope)` 직접 호출해 title·description 분기:
  - baseline(exclude): 원본 삭제가 아니라 귀사 범위 "기준 통제 제외"임이 드러나는 문구. 예) 제목 "기준 통제 제외 확인", 본문 "이 통제는 기준(baseline) 통제입니다. 삭제 시 귀사 범위에서 제외 처리되며 기준 자체는 보존됩니다."
  - tenant-add(soft_delete): 기존 일반 삭제 문구. 예) 제목 "통제 삭제 확인", 본문 "이 통제를 삭제합니다."
  - 문안은 위 의미를 담되 자연스럽게 다듬어도 됨.
- 실제 삭제 호출(onConfirm -> DELETE)은 기존 그대로. **문구만 분기**, 호출 경로 불변(단일 엔드포인트).

### (d) baseline 편집 안내 힌트 (선택 — UX 투명성)
- 통제 편집 진입 시 baseline이면 안내 노출:
  - `isBaseline(control.envelope)`로 판정.
  - 문안 예: "이 통제는 기준(baseline)입니다 — 저장 시 귀사 재정의(override)로 기록됩니다."
  - 위치: 편집 폼 상단 안내 배너 또는 편집 버튼 title 힌트 등, 저장 전 인지 가능한 자리. 기존 레이아웃 크게 흔들지 않는 선.
- **편집 자체는 막지 않음** — baseline이어도 폼 전체 편집 가능, 저장 시 서버가 override 처리. 순수 안내용.
- 구현 중 배치가 부자연스러우면 버튼 title 힌트 수준으로 축소 가능(판단 후 반영).

## 범위 밖 (하지 말 것)
- 새 mutation 훅·새 다이얼로그 컴포넌트 생성 금지(이미 존재).
- 편집 폼 필드 단위 잠금/분기 금지(서버가 override 처리).
- 삭제/수정 API 호출 경로 변경 금지(단일 엔드포인트 유지).
- **Excel 업로드 잠금 해제·13.6 버그 수정 금지**(별도 트랙).
- create/update/delete 외 bulk 편집·삭제 UI 금지.
- 백엔드/API 계약 변경 금지.
- `isTenantAdd`는 실사용처 강제하지 않음 — 정의만 유지되어도 무방(대칭성·테스트 목적).

## 완료 기준
- mutation 잠금 4곳 제거, 생성/편집/삭제 버튼 활성화. LOCK 외 disabled 조건(isPending 등)은 보존.
- `RCM_MUTATION_LOCKED` 명칭이 코드베이스에서 사라지고, Excel 잠금만 `EXCEL_UPLOAD_LOCKED`로 존치.
- 삭제 다이얼로그가 baseline/tenant에 따라 문구 분기.
- baseline 편집 진입 시 override 안내 노출(또는 축소 시 title 힌트).
- Excel 업로드 버튼은 여전히 잠금 상태.
- `sourceEnvelope.test.ts` 17건 통과 유지.
- `npm run build` TS 에러 0건.
- 콘솔 envelope 계약 위반 에러 0건.

## 브라우저 검증 항목 (사용자 수동 확인)
- 생성/편집/삭제 버튼 활성화 확인.
- baseline 통제 삭제 시도 -> 다이얼로그 "기준 통제 제외" 계열 문구.
- baseline 통제 편집 진입 -> override 안내 노출.
- Excel 업로드 버튼 여전히 비활성 확인.
- **실제 API 왕복 확인**: 생성/수정/삭제를 실제로 한 번씩 돌려 목록 자동 갱신(invalidate) 확인. tenant-add 통제를 실제로 만들면 삭제 다이얼로그의 tenant 분기 문구도 실제 확인 가능.
  - **주의**: 실제 mutation은 로컬 데이터를 변경함. 검증 후 baseline 상태로 복구하려면 `Set-Location E:\claudeprojects\ICFR` 후 `docker compose exec backend python -m seeds.seed_baseline --reset` 실행(모듈 실행 방식). 실제 왕복까지 확인할지, UI 활성화·문구만 볼지는 사용자 판단.

## PowerShell 5.1 제약 (엄수)
- `&&`, `||`, `|`, `$()`, `2>&1`, heredoc, `grep`, `head` 금지. 시퀀싱은 `;` 또는 개별 명령.
- 파일 검색은 `Select-String`. 경로 `E:\` 스타일, `Set-Location` 사용. 단일 명령 965바이트 미만.
- 테스트/빌드는 개별 명령: `Set-Location E:\claudeprojects\ICFR\frontend` 후 `npx vitest run <경로>` / `npm run build`(와일드카드 금지).

## 커밋
- 논리 단위 분리:
  - `feat(rcm): 통제 mutation 잠금 해제 + Excel 잠금 분리, 삭제/편집 source 분기 문구`
  - `docs(state): 2-A-3-2 mutation UI 배선 반영 (Excel 잠금 rename·isTenantAdd 미사용 기록)`
- mutation 잠금 해제가 실제 쓰기 경로를 여는 변경이므로 **브라우저 검증(버튼 활성화·문구 분기·실제 왕복) 후 push**. 검증 결과 확인 후 사용자 승인.

---
ICFR-PROMPT-2A3-2-mutation-ui-wiring.md 진행해줘
