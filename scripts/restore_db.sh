#!/usr/bin/env bash
# ICFR 백업 복구 리허설 — Object Storage → age 복호화 → 임시 DB restore
# 운영 DB($POSTGRES_DB)는 절대 건드리지 않는다. 임시 DB로만 복구한다.
#
# 사용:
#   restore_db.sh <age비밀키경로>              # 최신 객체 자동 선택
#   restore_db.sh <객체키> <age비밀키경로>      # 객체 지정
# 권한: root:icfr / 750
set -euo pipefail

ENV_FILE=/etc/icfr/.env
TMP_DIR=/data/backup/tmp
CONTAINER=icfr-postgres

if [ $# -eq 1 ]; then
    OBJECT_KEY=""
    KEY_FILE="$1"
elif [ $# -eq 2 ]; then
    OBJECT_KEY="$1"
    KEY_FILE="$2"
else
    echo "사용법: $0 [객체키] <age비밀키경로>" >&2
    exit 2
fi

[ -r "$KEY_FILE" ] || { echo "age 비밀키를 읽을 수 없다: $KEY_FILE" >&2; exit 2; }
[ -r "$ENV_FILE" ] || { echo "env 파일 없음: $ENV_FILE" >&2; exit 2; }

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

for v in POSTGRES_USER POSTGRES_DB BACKUP_S3_ENDPOINT BACKUP_S3_REGION BACKUP_S3_BUCKET \
         BACKUP_ACCESS_KEY BACKUP_SECRET_KEY; do
    [ -n "${!v:-}" ] || { echo "필수 환경변수 누락: $v" >&2; exit 2; }
done

export AWS_ACCESS_KEY_ID="$BACKUP_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$BACKUP_SECRET_KEY"
export AWS_DEFAULT_REGION="$BACKUP_S3_REGION"

mkdir -p "$TMP_DIR"

if [ -z "$OBJECT_KEY" ]; then
    OBJECT_KEY=$(aws --endpoint-url="$BACKUP_S3_ENDPOINT" s3api list-objects-v2 \
        --bucket "$BACKUP_S3_BUCKET" --prefix "db/" \
        --query 'reverse(sort_by(Contents,&LastModified))[0].Key' --output text)
    [ -n "$OBJECT_KEY" ] && [ "$OBJECT_KEY" != "None" ] || { echo "백업 객체가 없다" >&2; exit 1; }
    echo "최신 객체 자동 선택: $OBJECT_KEY"
fi

TS=$(TZ=Asia/Seoul date +%Y%m%d_%H%M%S)
TARGET_DB="icfr_restore_test_${TS}"

# 오조작 가드 — 운영 DB명이 대상이 되는 경우는 어떤 경로로도 허용하지 않는다.
if [ "$TARGET_DB" = "$POSTGRES_DB" ] || [ "$TARGET_DB" = "icfr_db" ]; then
    echo "대상 DB가 운영 DB($POSTGRES_DB)다. 중단한다." >&2
    exit 1
fi

ENC="$TMP_DIR/restore_${TS}.sql.gz.age"
GZ="$TMP_DIR/restore_${TS}.sql.gz"
SQL="$TMP_DIR/restore_${TS}.sql"

echo "[1/5] 다운로드: $OBJECT_KEY"
aws --endpoint-url="$BACKUP_S3_ENDPOINT" s3 cp "s3://${BACKUP_S3_BUCKET}/${OBJECT_KEY}" "$ENC" >/dev/null

echo "[2/5] 복호화"
age -d -i "$KEY_FILE" -o "$GZ" "$ENC"
rm -f "$ENC"

echo "[3/5] 압축 해제"
gunzip -c "$GZ" > "$SQL"
rm -f "$GZ"

echo "[4/5] 임시 DB 생성 및 restore: $TARGET_DB"
docker exec "$CONTAINER" createdb -U "$POSTGRES_USER" "$TARGET_DB"
docker exec -i "$CONTAINER" psql -q -U "$POSTGRES_USER" -d "$TARGET_DB" < "$SQL" > /dev/null
rm -f "$SQL"

echo "[5/5] baseline 5테이블 건수"
docker exec "$CONTAINER" psql -U "$POSTGRES_USER" -d "$TARGET_DB" -t -A -F'|' -c "
SELECT 'baseline_processes', count(*) FROM baseline_processes
UNION ALL SELECT 'baseline_sub_processes', count(*) FROM baseline_sub_processes
UNION ALL SELECT 'baseline_risks', count(*) FROM baseline_risks
UNION ALL SELECT 'baseline_controls', count(*) FROM baseline_controls
UNION ALL SELECT 'baseline_control_assertions', count(*) FROM baseline_control_assertions;"

echo
echo "임시 DB '$TARGET_DB' 는 자동 삭제하지 않는다. 대조 확인 후 직접 삭제할 것:"
echo "  docker exec $CONTAINER dropdb -U $POSTGRES_USER $TARGET_DB"
