# ICFR 운영 백업 라인 구축 (pg_dump → age → NCP Object Storage)

작성일: 2026-08-19
대상: 운영 서버 `icfr-prod-server` (101.79.21.122)
커밋 대상 경로: `scripts/`, `docs/adr/`

---

## 0. 배경과 완료 조건

운영 서버가 가동 중이고 baseline 실데이터가 올라가 있으나 백업이 0건이다.
본 작업은 **복구 리허설 통과까지**를 완료로 본다. 검증하지 않은 백업은 백업이 아니다.

**완료 조건 (전부 충족해야 완료)**
1. `scripts/backup_db.sh` 수동 실행 → Object Storage에 객체 1건 생성 확인
2. `scripts/restore_db.sh`로 그 객체를 내려받아 복호화 → 임시 DB에 restore 성공
3. 임시 DB의 baseline 5테이블 건수가 운영 DB와 **완전 일치**
4. cron 등록 확인 (`crontab -l` 출력으로 증명)
5. ADR-0028에 백업 섹션 추가 + 커밋

---

## 1. 사전 실측 (STEP 0 — 추정 금지)

작업 시작 전 아래를 **실제 조회**하고 결과를 기록한다. 추정한 값으로 진행하지 않는다.

```bash
# 1-1. baseline 테이블 실제 이름 확인
docker exec icfr-postgres psql -U icfr icfr_db -c "\dt" | grep -i baseline

# 1-2. 각 테이블 실제 건수 확인 (테이블명은 1-1 결과 사용)
docker exec icfr-postgres psql -U icfr icfr_db -c "
SELECT 'processes' t, count(*) FROM <실제_processes_테이블>
UNION ALL SELECT 'sub_processes', count(*) FROM <실제_sub_processes_테이블>
UNION ALL SELECT 'risks', count(*) FROM <실제_risks_테이블>
UNION ALL SELECT 'controls', count(*) FROM <실제_controls_테이블>
UNION ALL SELECT 'assertions', count(*) FROM <실제_assertions_테이블>;"

# 1-3. 서버 환경 확인
df -h /data
cat /etc/os-release | head -2
ls -l /etc/icfr/.env
```

기대값 참고: 8 / 29 / 85 / 93 / 469 (지난 세션 psql 직접 검증값).
**불일치 시 작업 중단하고 보고할 것.** 데이터가 변했다는 뜻이므로 원인 확인이 우선이다.

---

## 2. 도구 설치

```bash
apt-get update
apt-get install -y age awscli
age --version && aws --version
```

`awscli`가 apt 저장소 버전이라 구버전일 수 있다. `aws s3 cp` / `s3api list-objects-v2` /
`s3api delete-object` 3개 명령만 쓰므로 v1으로 충분하다. 동작 확인만 하고 넘어간다.

---

## 3. age 키 생성 및 배치 (중요)

**설계 원칙: 서버에는 공개키만 둔다.**
서버가 손상된 상황이 바로 백업을 쓸 상황이다. 비밀키를 서버에 두면 서버와 함께 잃는다.

```bash
# 서버에서 키쌍 생성
age-keygen -o /tmp/icfr-backup-age.key
# 출력되는 public key(age1...로 시작)를 기록
cat /tmp/icfr-backup-age.key
```

- **공개키**: `/etc/icfr/.env`에 `BACKUP_AGE_PUBKEY=age1...` 로 저장
- **비밀키**: 파일 전체 내용을 마스터에게 출력하여 전달 → 마스터가 로컬 + 별도 보관처
  2곳에 보관 → **확인 회신 받은 뒤** 서버에서 `shred -u /tmp/icfr-backup-age.key`로 삭제

> Claude Code는 비밀키를 어떤 파일에도 영구 저장하지 말 것.
> 마스터 보관 확인 전까지는 `/tmp` 파일을 삭제하지 말고 대기한다.

---

## 4. `/etc/icfr/.env` 추가 항목

기존 파일에 **append만** 한다 (기존 값 수정 금지).
파일 권한은 기존과 동일하게 유지: 소유 `root:icfr`, 모드 `640`.

```
# --- backup ---
BACKUP_S3_ENDPOINT=https://kr.object.ncloudstorage.com
BACKUP_S3_REGION=kr-standard
BACKUP_S3_BUCKET=icfr-backup
BACKUP_ACCESS_KEY=<마스터가 직접 입력>
BACKUP_SECRET_KEY=<마스터가 직접 입력>
BACKUP_AGE_PUBKEY=age1...
BACKUP_RETENTION_DAYS=90
```

`BACKUP_ACCESS_KEY` / `BACKUP_SECRET_KEY`는 **마스터가 직접 입력**한다.
Claude Code는 자리표시자만 넣고, 마스터 입력 후 재개한다.

---

## 5. `scripts/backup_db.sh` 신규

ADR-0020 제로 추상화 원칙 준수 — 함수 분리·추상화 없이 순차 실행 스크립트로 작성한다.

**동작 순서**
1. `set -euo pipefail` + `/etc/icfr/.env` 로드
2. 필수 환경변수 누락 시 즉시 실패 (조용한 성공 금지)
3. `docker exec icfr-postgres pg_dump -U icfr icfr_db` → `gzip` → `age -r $BACKUP_AGE_PUBKEY`
   → `/data/backup/tmp/` 에 저장
   - **파이프 중간 실패를 잡을 것.** `pipefail` 만으로 부족하면 임시파일 단계 분리
   - dump 결과 크기가 1KB 미만이면 실패 처리 (빈 덤프 업로드 방지)
4. 객체 키: `db/YYYY/MM/icfr_db_YYYYMMDD_HHMMSS.sql.gz.age` (KST 기준)
5. `aws --endpoint-url=$BACKUP_S3_ENDPOINT s3 cp` 로 업로드
6. **업로드 검증**: `s3api head-object`로 존재 + 크기 일치 확인. 불일치 시 실패
7. 검증 통과 후에만 로컬 임시파일 삭제
8. 보존정책: `s3api list-objects-v2 --prefix db/` 로 목록 조회 →
   `LastModified`가 `BACKUP_RETENTION_DAYS`일 초과인 객체만 `delete-object`
   - **삭제 대상 판정은 LastModified 타임스탬프로만 한다. 파일명 문자열 파싱 금지** (회귀 방지 원칙 1)
   - 삭제 건수를 로그에 남길 것
9. 결과 기록:
   - 로그: `/data/backup/log/backup_YYYYMM.log` (월별 파일, append)
   - 상태: `/data/backup/LAST_RESULT` 에 `OK <ISO시각> <객체키> <바이트>` 또는
     `FAIL <ISO시각> <실패단계>` 를 **덮어쓰기**로 기록
10. 실패 시 exit code 비0

**주의**
- `.env`에 시크릿이 있으므로 스크립트에서 `set -x` 사용 금지
- AWS 자격증명은 환경변수(`AWS_ACCESS_KEY_ID` 등)로 전달, 명령행 인자 금지 (`ps` 노출 방지)
- 스크립트 권한: `root:icfr` / `750`

---

## 6. `scripts/restore_db.sh` 신규

**운영 DB를 절대 건드리지 않는다.** 임시 DB로만 restore한다.

- 인자: 객체 키 (미지정 시 가장 최근 객체 자동 선택)
- 인자: age 비밀키 파일 경로 (필수, 기본값 없음)
- 동작: 다운로드 → `age -d -i <키파일>` → `gunzip` → 임시 DB 생성 후 `psql` restore
- 임시 DB명: `icfr_restore_test_<타임스탬프>` — 고정명 금지(재실행 충돌 방지)
- restore 후 baseline 5테이블 건수를 출력
- **스크립트 시작 시 대상 DB명이 `icfr_db`면 즉시 중단** (오조작 가드)
- 스크립트 종료 시 임시 DB를 자동 삭제하지 **않는다**. 마스터가 확인 후 직접 삭제.
  삭제 명령을 화면에 안내 출력할 것.

---

## 7. 복구 리허설 (필수 실행)

```bash
# 1) 백업 1회 수동 실행
/opt/icfr/scripts/backup_db.sh; echo "exit=$?"
cat /data/backup/LAST_RESULT

# 2) Object Storage 객체 확인
aws --endpoint-url=https://kr.object.ncloudstorage.com s3 ls s3://icfr-backup/db/ --recursive

# 3) 복구 실행 (비밀키는 마스터가 임시 업로드 후 즉시 삭제)
/opt/icfr/scripts/restore_db.sh <객체키> <비밀키경로>

# 4) 건수 대조 — 운영 DB와 임시 DB가 완전 일치해야 함
```

**4번 결과를 운영 DB 실측값(STEP 0의 1-2)과 나란히 출력하여 보고할 것.**
한 건이라도 다르면 완료가 아니다.

리허설 후 비밀키 임시 파일은 `shred -u`로 삭제한다.

---

## 8. cron 등록

```
0 3 * * * /opt/icfr/scripts/backup_db.sh >> /data/backup/log/cron.log 2>&1
```

- root crontab에 등록. 서버 타임존이 KST인지 `timedatectl`로 확인 후 등록할 것
  (UTC면 18:00으로 등록하거나 타임존을 Asia/Seoul로 변경 — 어느 쪽을 택했는지 로그에 명시)
- `logrotate` 설정 추가: `/data/backup/log/*.log`, 월 단위, 12개월 보관, compress

---

## 9. 문서

`docs/adr/ADR-0028`에 **백업 섹션만** 추가한다 (문서 전체 갱신은 별도 작업).

포함 내용:
- 버킷 `icfr-backup`, 잠금 비활성 / 암호화 비활성 / 비공개 — **선택 근거 명시**
  - NCP Object Storage 암호화는 SSE-C(고객 제공 키) 방식이라 서버에 키를 평문 보관하게 됨.
    age로 파일 자체를 암호화하는 편이 보호 강도가 높고 키 관리 지점이 하나로 유지됨
  - 객체 잠금(WORM)은 삭제가 물리적으로 불가능해지므로, 백업 프로세스가 안정화되고
    파일명 규칙이 확정된 뒤 별도 판단으로 활성화 (현재 보류, 사유 기록)
- age 키 분리 보관 구조 (서버=공개키, 비밀키=마스터 2곳)
- 보존 90일 근거: 실측 백업 크기 34,918바이트 → 90일 보존 시 월 요금 0.1원 미만.
  비용이 사실상 0이므로 감사 대응(과거 시점 복원 요구)을 위해 90일 채택
- Lifecycle을 콘솔이 아닌 **스크립트로 구현한 이유**: 고객사 이관 시 코드로 재현 가능해야 함
- 복구 리허설 결과(실행일, 대조 건수)
- MinIO 증빙 백업은 범위 외 — 보존정책이 다르므로 별도 설계 예정

---

## 10. 커밋

- `scripts/backup_db.sh`, `scripts/restore_db.sh`, ADR 수정분을 **명시적 경로로** `git add`
- 커밋 전 `git pull --no-rebase` (Regina 작업 반영)
- 한 커밋 = 한 원인 원칙에 따라 분리:
  1. `feat(ops): DB 백업·복구 스크립트 추가`
  2. `docs(adr): ADR-0028 백업 섹션 추가`
- **`.env` 실제 값과 age 비밀키는 절대 커밋 금지.** 커밋 전 `git diff --staged`로 확인

---

## 11. 보고 형식

작업 완료 후 아래를 그대로 출력한다.

1. STEP 0 실측 건수 (5개)
2. 백업 실행 exit code + `LAST_RESULT` 내용
3. Object Storage 객체 목록 (`s3 ls` 원문)
4. 복구 후 임시 DB 건수 (5개) — 1번과 나란히
5. `crontab -l` 출력
6. `timedatectl`에서 확인한 타임존과 cron 시각 선택 근거
7. 커밋 해시 2건

**실행하지 않은 항목을 완료로 보고하지 않는다.** 막힌 지점은 막힌 대로 보고할 것.
