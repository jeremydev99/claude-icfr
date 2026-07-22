# ICFR-PROMPT: 어댑터 source envelope 흡수 준비

## 목표
TrustBuilder가 2-B(baseline/overlay + resolver 병합)를 백엔드에 완료했고, **Q2(id 이원화)의 최종 답이 `source envelope`로 확정**됨. 이 프롬프트는 프론트 어댑터 계층에 envelope 흡수 "자리"를 미리 잡아두는 준비 작업이다.

> ⚠️ **실제 API는 아직 전환 전(2-A-3 미도래).** 지금은 계약 스펙만 확정된 상태다. 따라서 **envelope 필드는 optional**로 넣고, UI/mutation은 건드리지 않는다. 실제 연결은 2-A-3 "연결 시작" 신호가 온 뒤 별도 작업.

## 핵심 원칙 (반드시 준수)
1. **스펙 우선**: envelope 4필드 규약은 확정됐으나 런타임 응답은 아직 미전환. → 지금은 **optional**, 2-A-3 전환 후 required로 조인다.
2. **추정 금지**: 어댑터·타입 파일 위치와 기존 `ControlSearchOut` 대응 프론트 타입 구조를 **실제로 읽어 확인한 뒤** 작업한다.
3. **회귀 위험 0**: UI 컴포넌트, mutation 훅, 쿼리 키는 이번 작업에서 변경하지 않는다. 타입 + 어댑터 매핑 + 순수 헬퍼만 추가.

## source envelope 규약 (확정)
resolved 항목마다 실리는 메타. **process / sub_process / risk / control 4계층 공통**:

| 필드 | 타입 | 의미 |
|---|---|---|
| `id` | string | 정체성 id (baseline 유래=baseline id, add=instance id) |
| `source` | `"baseline" \| "tenant"` | baseline 유래 vs 회사 add |
| `baseline_id` | string \| null | baseline 유래면 그 id, add면 null |
| `is_overridden` | boolean | override 적용 시 true, adopt/add는 false |

- 응답 shape: 기존 `ControlSearchOut`(및 각 계층 목록 타입) 필드는 **그대로 유지** + envelope 4필드만 얹힘. 어댑터는 항등 매핑에 envelope 매핑만 추가.
- 편집·삭제 라우팅은 `source`로 판별한다.
- 삭제 의미론(문서화용, 이번엔 헬퍼 시그니처만): baseline→exclude(hide), add→soft delete. 전 계층 공통.

---

## 0단계 — 사전 확인 (읽기 전용, 추정 금지)
아래를 실제로 확인하고 결과를 짧게 보고한 뒤 진행:
1. 어댑터 계층 파일 위치와 패턴 (control 어댑터부터). process/sub_process/risk 어댑터가 계층별로 분리돼 있는지, 공통 유틸을 쓰는지 확인.
2. 기존 `ControlSearchOut` 대응 프론트 타입 정의 위치(관계 필드 `process_code`/`sub_process_code`/`risk_level`/`assertions` 포함 여부 확인).
3. 4계층 resolved/목록 타입이 어디에 정의돼 있는지, 공통 타입 파일이 있는지.

## 1단계 — 공통 타입 정의
- `SourceEnvelope` 타입을 **한 곳에** 정의 (4계층 공통이므로 중복 정의 금지):
  ```ts
  export interface SourceEnvelope {
    id: string;
    source: "baseline" | "tenant";
    baseline_id: string | null;
    is_overridden: boolean;
  }
  ```
- 위치는 0단계에서 확인한 공통 타입 파일에 배치.

## 2단계 — 4계층 타입에 optional로 얹기
- process / sub_process / risk / control 각 resolved(목록) 타입에 `envelope?: SourceEnvelope` 를 **optional**로 추가.
- 기존 필드는 손대지 않는다.

## 3단계 — 어댑터 항등 매핑 + 안전 폴백
- 각 계층 어댑터의 항등 매핑에 envelope 매핑 추가.
- **부재 시 폴백**: 현재 API는 아직 envelope를 안 보내므로, 응답에 envelope 필드가 없으면 `envelope`를 `undefined`로 두거나(또는 `id`만 있는 최소 폴백), 절대 throw하지 않게 방어적으로 매핑.

## 4단계 — source 기반 라우팅 헬퍼 (순수 함수만)
- `source` 값으로 편집/삭제 경로를 판별하는 **순수 헬퍼**만 준비. 실제 mutation 호출은 연결하지 않는다.
  - 예: `isBaseline(env)`, `isTenantAdd(env)`, `resolveDeleteSemantics(env)` → `"exclude" | "soft_delete"` 반환.
- 헬퍼는 envelope 부재(undefined) 시 안전한 기본값을 반환하도록 처리.

---

## 검증
- `npm run build` (tsc 타입체크 통과)가 검증 기준. **UI 변화 없으므로 브라우저 확인 불필요.**
- 기존 타입과의 충돌 없음 확인(envelope는 optional이라 기존 응답과 어긋나지 않아야 함).

## git
- 저위험 준비 작업 → **자동 push 승인**.
- feature 브랜치 → `npm run build` 통과 → `--no-ff` 머지 → main push.
- 커밋 메시지에 "2-A-3 envelope 흡수 자리 준비 (스펙 확정, API 미전환·optional)" 취지 명시.
- 머지 후 `ClaudeICFR.md` 섹션 12/14 상태 업데이트.

## 환경 제약
- Windows 10 / PowerShell 5.1 / VS Code 통합 터미널.
- `&&` `||` `$()` `&`(백그라운드) `/dev/null` heredoc `grep` 금지. `cd` 대신 `Set-Location`. 복합 명령 분리.

---
**ICFR-PROMPT-envelope-adapter-prep.md 진행해줘**
