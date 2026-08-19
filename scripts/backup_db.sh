#!/usr/bin/env bash
# ICFR 운영 DB 백업 — pg_dump → gzip → age(공개키) → NCP Object Storage
# 실행: /opt/icfr/scripts/backup_db.sh   (root, cron 새벽 1회)
# 권한: root:icfr / 750
# set -x 금지 — /etc/icfr/.env 의 시크릿이 로그에 남는다.
set -euo pipefail

ENV_FILE=/etc/icfr/.env
TMP_DIR=/data/backup/tmp
LOG_DIR=/data/backup/log
LAST_RESULT=/data/backup/LAST_RESULT
CONTAINER=icfr-postgres

STAGE="init"
STAMP_ISO=$(TZ=Asia/Seoul date --iso-8601=seconds)
LOG_FILE="$LOG_DIR/backup_$(TZ=Asia/Seoul date +%Y%m).log"

mkdir -p "$TMP_DIR" "$LOG_DIR"

log() { echo "[$(TZ=Asia/Seoul date --iso-8601=seconds)] $*" >> "$LOG_FILE"; }

fail() {
    echo "FAIL $(TZ=Asia/Seoul date --iso-8601=seconds) $STAGE" > "$LAST_RESULT"
    log "FAIL stage=$STAGE"
    exit 1
}
trap fail ERR

STAGE="load_env"
[ -r "$ENV_FILE" ] || { log "env 파일 없음: $ENV_FILE"; fail; }
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

STAGE="check_env"
for v in POSTGRES_USER POSTGRES_DB BACKUP_S3_ENDPOINT BACKUP_S3_REGION BACKUP_S3_BUCKET \
         BACKUP_ACCESS_KEY BACKUP_SECRET_KEY BACKUP_AGE_PUBKEY BACKUP_RETENTION_DAYS; do
    if [ -z "${!v:-}" ]; then
        log "필수 환경변수 누락: $v"
        fail
    fi
done

export AWS_ACCESS_KEY_ID="$BACKUP_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$BACKUP_SECRET_KEY"
export AWS_DEFAULT_REGION="$BACKUP_S3_REGION"

TS=$(TZ=Asia/Seoul date +%Y%m%d_%H%M%S)
YEAR=$(TZ=Asia/Seoul date +%Y)
MONTH=$(TZ=Asia/Seoul date +%m)
BASE="icfr_db_${TS}.sql.gz.age"
OBJECT_KEY="db/${YEAR}/${MONTH}/${BASE}"

RAW="$TMP_DIR/icfr_db_${TS}.sql"
GZ="$RAW.gz"
ENC="$GZ.age"

# 파이프 중간 실패를 확실히 잡기 위해 단계별 임시파일로 분리한다.
STAGE="pg_dump"
docker exec "$CONTAINER" pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$RAW"

STAGE="size_check"
RAW_SIZE=$(stat -c %s "$RAW")
if [ "$RAW_SIZE" -lt 1024 ]; then
    log "덤프 크기 비정상: ${RAW_SIZE}바이트 (< 1024)"
    rm -f "$RAW"
    fail
fi
log "pg_dump OK ${RAW_SIZE}바이트"

STAGE="gzip"
gzip -c "$RAW" > "$GZ"
rm -f "$RAW"

STAGE="encrypt"
age -r "$BACKUP_AGE_PUBKEY" -o "$ENC" "$GZ"
rm -f "$GZ"
ENC_SIZE=$(stat -c %s "$ENC")

STAGE="upload"
aws --endpoint-url="$BACKUP_S3_ENDPOINT" s3 cp "$ENC" "s3://${BACKUP_S3_BUCKET}/${OBJECT_KEY}" >/dev/null

STAGE="verify_upload"
REMOTE_SIZE=$(aws --endpoint-url="$BACKUP_S3_ENDPOINT" s3api head-object \
    --bucket "$BACKUP_S3_BUCKET" --key "$OBJECT_KEY" --query 'ContentLength' --output text)
if [ "$REMOTE_SIZE" != "$ENC_SIZE" ]; then
    log "업로드 크기 불일치 local=$ENC_SIZE remote=$REMOTE_SIZE key=$OBJECT_KEY"
    fail
fi
log "upload OK key=$OBJECT_KEY size=$ENC_SIZE"

STAGE="cleanup_tmp"
rm -f "$ENC"

# 보존정책 — 삭제 판정은 LastModified 타임스탬프로만 한다(파일명 파싱 금지).
STAGE="retention"
CUTOFF=$(date -d "-${BACKUP_RETENTION_DAYS} days" +%s)
DELETED=0
while read -r key lm; do
    [ -n "$key" ] || continue
    lm_epoch=$(date -d "$lm" +%s)
    if [ "$lm_epoch" -lt "$CUTOFF" ]; then
        aws --endpoint-url="$BACKUP_S3_ENDPOINT" s3api delete-object \
            --bucket "$BACKUP_S3_BUCKET" --key "$key" >/dev/null
        log "retention 삭제 key=$key lastmodified=$lm"
        DELETED=$((DELETED + 1))
    fi
done < <(aws --endpoint-url="$BACKUP_S3_ENDPOINT" s3api list-objects-v2 \
    --bucket "$BACKUP_S3_BUCKET" --prefix "db/" \
    --query 'Contents[].[Key,LastModified]' --output text)
log "retention 완료 삭제 ${DELETED}건 (보존 ${BACKUP_RETENTION_DAYS}일)"

STAGE="done"
trap - ERR
echo "OK $(TZ=Asia/Seoul date --iso-8601=seconds) $OBJECT_KEY $ENC_SIZE" > "$LAST_RESULT"
log "OK key=$OBJECT_KEY size=$ENC_SIZE 삭제=${DELETED}건"
exit 0
