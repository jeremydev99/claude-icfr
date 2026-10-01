# ADR-0035 — 매뉴얼 패널 문구 저장 구조 (7-A)

- **날짜**: 2026-09-28
- **상태**: 채택 (7-A 백엔드 틀·키 규칙·문구 초안 범위)
- **관련**: `ClaudeICFR.md` 13.9-8(범위·배치·구조 재결정, 2026-09-22), ADR-0036(감사 컬럼 행위자)

## 배경

용어·화면 설명을 사용자에게 보여주는 매뉴얼 패널을 만들기로 했다(13.9-8). 이 ADR은
그중 **저장 구조와 키 규칙**만 다룬다. 우측 패널 UI(본문 밀림·폭 조절·좁은 화면 겹침)는
7-B, 문구 편집 API 는 7-C 로 범위를 나눈다.

## 결정

### 1. 테이블은 `help_texts` 하나

`IdentityBase`(tenant 비종속) — 도움말은 제품이 제공하는 문구이지 회사 데이터가 아니다.
`scoping_templates` 와 같은 자리다. 컬럼: `key`·`locale`(현재 `ko` 고정)·`title`·`body`·
`source`·`as_of`·`baseline_version`·`sort_order`. unique 는 `(key, locale)` 부분 유니크
(`WHERE NOT is_deleted`).

`source`/`as_of` 는 규정을 인용할 때만 채운다(13.9-8 — 기준일 없는 규정 설명은 낡은
판단을 유도한다). `source` 가 있으면 `as_of` 도 있어야 하며, 이 검증은 DB 제약이 아니라
시드 로더(`seeds/seed_help_texts.py`)가 한다.

**회사별 문구 수정(overlay)은 이 단계에 없다.** 키가 전역 고유하므로, 필요해지면
`help_text_overlays`(tenant_id + help_text_id FK) 테이블만 추가하면 된다 — `help_texts`
자체는 바뀌지 않는다.

### 2. 키는 불투명한 식별자다

키 규칙은 다섯 접두사를 **권장**한다 — `menu.<route>` / `screen.<route>.<섹션>` /
`field.<모듈>.<API 필드명>` / `action.<모듈>.<동작>` / `term.<용어>`. 문자는 소문자·숫자·
`_`·`-`·`.`만 허용한다(`core/help_keys.KEY_PATTERN`). `/`가 들어가는 route(`admin/departments`)
는 `.`로 바꿔 쓴다(`menu.admin.departments`).

**하지만 이 접두사 구조를 코드가 해석하지 않는다.** `core/help_keys.py`·`api/help.py` 는
키를 점으로 쪼개 route 나 섹션 이름을 뽑아내지 않는다. 조회는 **접두사 문자열 일치**
(`key == prefix` 이거나 `key LIKE prefix || '.%'`)만 쓴다. 키 구조를 해석하는 코드가
생기면 화면 이름이 바뀔 때마다 저장소와 조회 로직을 함께 고쳐야 한다 — 그 결합을
만들지 않는 것이 이 규칙의 목적이다. `_`는 유효한 키 문자이자 SQL LIKE 의 와일드카드이므로
접두사 조회 시 반드시 이스케이프한다.

### 3. 문구 원본은 데이터 파일

`backend/seeds/data/help_texts_ko.json` 이 콘텐츠의 단일 원천이다. `seeds/seed_help_texts.py`
가 이 파일을 읽어 멱등 upsert 한다 — 값이 바뀐 필드만 갱신하고, 파일에서 빠진 키는
소프트 삭제한다. **쓰기 API 는 없다.** 문구 수정은 파일을 고치고 시드를 다시 돌리는 것으로
한다. 행위자는 `system:seed-help`(ADR-0036).

### 4. 조회 API만 만든다

`GET /api/help?prefix=` (접두사 일괄 조회) · `GET /api/help/{key}` (단건, 없으면 404).
인증만 요구한다(`get_current_user`) — 외부감사인을 포함한 전 역할이 읽을 수 있다.
쓰기는 7-C 범위다.

### 5. 이번 시드 범위

`menu.*`·`screen.*`·`term.*` 만 채운다. `field.*`·`action.*` 는 규칙만 정의하고 문구는
넣지 않는다(각 모듈 작업에서 붙인다). 화면이 없는 메뉴(`schedule`·`report`·`notification`·
`admin.role-assignments`·`admin.policies`·`admin.fiscal-year`)는 키만 만들고 `title`·`body`
는 비워 둔다 — 지어내지 않는다.

### 6. 테스트 실행 환경 — 운영 이미지 안에서 pytest 는 지원하지 않는다

`menu.*` 1:1 검증 테스트가 `frontend/src/config/navigation.ts` 를 직접 읽는다. 저장소
전체를 받은 환경(`ci.yml`·`deploy.yml`·로컬 `dev.ps1 test`)에서만 통과하며, 백엔드
이미지만으로 실행하는 환경(운영 컨테이너 안에서 `docker compose exec backend pytest`)은
이 파일이 없어 실패한다 — **운영 이미지 안에서 pytest 실행은 지원 대상이 아니다.**
`dev.ps1 test`는 호스트에서 `backend/` 가상환경으로 pytest 를 실행하도록 CI 와
같은 방식으로 맞췄다(2026-09-28).

## 하지 않은 것 (백로그)

- 우측 패널 UI — 7-B
- 문구 편집 API — 7-C
- `field.*`·`action.*` 콘텐츠 — 각 모듈 작업에서
- 회사별 문구 오버레이 테이블 — 필요해지면 추가
- 용어집(§11) 확장(설계평가·운영평가·통제유형·미비점 등) — 별건, `ClaudeICFR.md` 백로그
- 시드별 출처명(`created_by` 값) 기록을 검증하는 공통 테스트 — 13.9-51 후속
- 운영 이미지에서 `tests/` 디렉토리 제외 검토
