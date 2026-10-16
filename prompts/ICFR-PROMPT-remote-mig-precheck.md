# ICFR-PROMPT-remote-mig-precheck

## 목적
원격에서 들어온 alembic 2건(d6e7f8a9b0c1, e7f8a9b0c1d2, 둘 다 부분 유니크 인덱스 추가)을
로컬 DB에 적용하기 **전에**, (a) 두 파일 내용을 읽고 (b) 대상 테이블의 **중복 행 여부**를 조회해
인덱스 생성이 실패할 소지가 없는지 확인한다.
이번 프롬프트는 **읽기 전용**. 이미지 재빌드·alembic 실행·DB 쓰기·git 변경 절대 금지.

## 엄격 제약 (반드시 준수)
- 읽기 전용. `alembic upgrade`·`docker compose build`·DDL·INSERT/UPDATE/DELETE 금지.
- 조회는 컨테이너 안: `docker compose exec -T postgres psql -U icfr_user -d icfr_db ...`
- 잘림 방지: `-A -t` 로 뽑아 파일로 저장 후 읽어 보고.
- 유니크 대상 컬럼·조건은 **추정 금지** — 단계 1에서 마이그레이션 파일을 읽어 실제 인덱스 정의(대상 테이블·컬럼·WHERE 부분조건)를 확인한 뒤, 그 정의대로 단계 2 중복 조회를 짠다.
- PowerShell 5.1: `&&` 금지(`;`), heredoc·`2>&1`·`$()` 금지, `cd` 대신 `Set-Location`, 단일 명령 965B 이하.

## 준비
```
Set-Location E:\claudeprojects\ICFR
New-Item -ItemType Directory -Force -Path E:\claudeprojects\ICFR\_probe
```

## 단계 1 — 두 마이그레이션 파일 읽기
`backend/alembic/versions/`(또는 프로젝트의 versions 경로) 에서 아래 2개를 찾아 내용을 읽는다.
- `*d6e7f8a9b0c1*` (user_roles 유니크)
- `*e7f8a9b0c1d2*` (부서·소속 유니크)
각 파일에서 확인할 것:
- `down_revision` 체인: c5d6e7f8a9b0 → d6e7f8a9b0c1 → e7f8a9b0c1d2 (head) 인지.
- upgrade() 가 만드는 인덱스: **대상 테이블 · 컬럼 목록 · UNIQUE 여부 · WHERE 부분조건**(partial index 조건).
- downgrade() 가 그 인덱스를 제거하는지.
읽은 정의를 `_probe\pc1_migdefs.txt` 로 요약 저장(파일 경로·인덱스명·테이블·컬럼·조건).

## 단계 2 — 대상 테이블 중복 조회 (단계 1 정의대로)
각 부분 유니크 인덱스에 대해, **그 인덱스가 유일성을 요구하는 컬럼 조합 + WHERE 조건** 범위에서
중복이 있는지 센다. 예시 형태(실제 컬럼/조건은 단계 1 값으로 치환, 추정 금지):
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT <키컬럼들>, count(*) FROM <테이블> WHERE <부분조건> GROUP BY <키컬럼들> HAVING count(*) > 1;" > E:\claudeprojects\ICFR\_probe\pc2_<테이블>.txt
```
- 결과가 **비어 있으면**(중복 0) 해당 인덱스는 깨끗이 생성됨.
- 한 줄이라도 나오면 그 키/건수를 보고 — 재빌드 시 인덱스 생성이 **실패**하므로 진행 전에 처리 필요.

## 단계 3 — alembic 상태 재확인 (읽기)
```
docker compose exec -T backend alembic current ; docker compose exec -T backend alembic heads
```
- 컨테이너가 아는 head(c5d6e7f8a9b0)와 저장소 체인 head(e7f8a9b0c1d2)의 격차 재확인.
- 재빌드 시 컨테이너 startup 에서 이 2건이 순서대로 적용됨을 명시.

## 산출 (보고 형식)
1. 두 마이그레이션의 down_revision 체인 정합(c5→d6→e7) 확인.
2. 각 인덱스: 테이블·컬럼·부분조건·UNIQUE 여부 요약.
3. 중복 조회 결과: 인덱스별 중복 0 / 있으면 키·건수. **재빌드 안전 여부 한 줄 판정.**
4. alembic current/heads 격차 재확인.
5. DB·이미지·git 무변경, `_probe\pc*.txt` 만 생성 명시.
6. 판정에 따른 다음 단계:
   - 중복 0 → 이미지 재빌드로 2건 적용해도 안전 → 이후 단계 B(백필 마이그레이션 작성) 진행 승인 요청.
   - 중복 있음 → 재빌드 전 그 중복 처리 방침부터 결정 필요(임의 수정 금지, 보고만).
