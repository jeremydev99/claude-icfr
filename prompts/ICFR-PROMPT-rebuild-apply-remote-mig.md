# ICFR-PROMPT-rebuild-apply-remote-mig

## 목적
backend 이미지를 재빌드해 pull 로 들어온 alembic 2건(d6e7f8a9b0c1, e7f8a9b0c1d2)을
**로컬 DB 에 적용**하고, head 가 e7f8a9b0c1d2 로 올라갔는지·4개 부분 유니크 인덱스가 생겼는지 검증한다.
사전 점검(remote-mig-precheck)에서 중복 0·DROP 대상 존재·이름 미충돌 확인됨.
**로컬 한정** — 운영 접속·git push 금지. 새 마이그레이션 작성은 이 프롬프트 범위 밖(단계 B).

## 엄격 제약 (반드시 준수)
- 대상은 **로컬** 스택. 운영 DB·운영 배포 접근 금지. git 변경·push 금지.
- 적용 전 DB 백업(대상 3테이블 + alembic_version)을 `_probe` 에 `\copy`+`docker compose cp` 로 남긴다(Out-File 금지).
- alembic 은 **재빌드 후 컨테이너 startup 의 upgrade** 로만 적용. 수동 `alembic downgrade`·임의 DDL 금지.
- upgrade 가 실패하면(인덱스 생성 등) **멈추고 로그 보고**. 강행·재시도·임의 데이터 수정 금지.
- PowerShell 5.1: `&&` 금지(`;`), heredoc·`2>&1`·`$()` 금지, `cd` 대신 `Set-Location`, 단일 명령 965B 이하.

## 준비
```
Set-Location E:\claudeprojects\ICFR
New-Item -ItemType Directory -Force -Path E:\claudeprojects\ICFR\_probe
```

## 단계 0 — 적용 전 상태·백업
현재 head 재확인:
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT version_num FROM alembic_version;" > E:\claudeprojects\ICFR\_probe\rb0_head_before.txt
```
대상 테이블 백업(컨테이너 안 \copy → host 로 cp). 3테이블 각각:
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -c "\copy user_roles TO '/tmp/rb_user_roles.csv' WITH CSV HEADER"
docker compose cp postgres:/tmp/rb_user_roles.csv E:\claudeprojects\ICFR\_probe\rb_user_roles.csv
```
departments, user_departments 도 동일 패턴으로 백업. (departments/user_departments 는 0행이라 헤더만 나올 수 있음 — 정상.)
백업 파일 존재·행수 확인 후 진행.

## 단계 1 — 재빌드
```
docker compose build backend
```
빌드 성공 확인. 실패면 멈추고 로그 보고.

## 단계 2 — 재기동 (startup 에서 alembic upgrade head 실행)
```
docker compose up -d backend
```
startup 로그에서 alembic 이 d6e7f8a9b0c1 → e7f8a9b0c1d2 순으로 적용되는지 확인:
```
docker compose logs --tail=80 backend > E:\claudeprojects\ICFR\_probe\rb2_startup.txt
```
- 로그에 upgrade 성공(두 리비전 적용)·에러 없음 확인. 에러면 멈추고 보고(백업으로 복구 가능).
- backend healthy 재확인:
```
docker compose ps backend
```

## 단계 3 — 검증 (읽기)
head 가 올라갔는지:
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT version_num FROM alembic_version;" > E:\claudeprojects\ICFR\_probe\rb3_head_after.txt
```
→ e7f8a9b0c1d2 여야 한다.
4개 부분 유니크 인덱스 실재 확인:
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT indexname, tablename FROM pg_indexes WHERE indexname IN ('uq_user_roles_active_pair','uq_departments_tenant_name','uq_user_departments_pair','uq_user_departments_one_primary') ORDER BY 1;" > E:\claudeprojects\ICFR\_probe\rb3_indexes.txt
```
→ 4건 모두 나와야 한다.
데이터 보존 확인(백필 대상 테이블 무손상):
```
docker compose exec -T postgres psql -U icfr_user -d icfr_db -A -t -c "SELECT 'user_roles', count(*) FROM user_roles UNION ALL SELECT 'controls', count(*) FROM controls UNION ALL SELECT 'baseline_controls', count(*) FROM baseline_controls UNION ALL SELECT 'control_assertions', count(*) FROM control_assertions;" > E:\claudeprojects\ICFR\_probe\rb3_counts.txt
```
→ user_roles 3, controls 98, baseline_controls 93, control_assertions 469 유지 확인.

## 산출 (보고 형식)
1. 적용 전 head(c5d6e7f8a9b0) / 백업 3파일 경로·행수.
2. 재빌드 성공 여부, startup alembic 적용 로그 요약(2건 적용·에러 유무).
3. 적용 후 head = e7f8a9b0c1d2 확인, 4개 인덱스 존재 확인.
4. 데이터 보존 카운트(user_roles 3 / controls 98 / baseline 93 / assertions 469).
5. **git·운영 무변경, push 안 함** 명시. `_probe\rb*` 만 생성.
6. 다음 단계 안내: 이어서 `testfk-migration.md` 단계 B — B1 은 down_revision=**e7f8a9b0c1d2**, 단계 C 검증 기대값 control_assertions=**469**.
