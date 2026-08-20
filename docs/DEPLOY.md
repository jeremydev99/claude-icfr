# ICFR 운영 배포 가이드

- 도메인: `https://icfr.synap.co.kr` (A → 101.79.21.122)
- 서버: Ubuntu 24.04 / 2vCPU / 8GB, 데이터 디스크 `/dev/vdb` → `/data`
- 레지스트리: GHCR `ghcr.io/jeremydev99/claude-icfr/{backend,frontend}`
- 이미지 태그: **커밋 SHA 고정** (`latest` 미사용 — 롤백 대상을 특정하기 위함)

| 구성요소 | 위치 | 외부 노출 |
|---|---|---|
| 호스트 nginx | `/etc/nginx/sites-enabled/icfr.conf` | 80 / 443 |
| frontend 컨테이너 | `127.0.0.1:8080` → 컨테이너 80 | 없음 |
| backend 컨테이너 | `127.0.0.1:8000` | 없음 |
| postgres / minio | `127.0.0.1:5432` / `9000`,`9001` | 없음 |
| 데이터 | `/data/postgres`, `/data/minio` (바인드 마운트) | — |

> ⚠️ **서버에서 파일을 직접 수정하지 말 것.** `docker-compose.prod.yml` 은 배포 시 리포에서
> 다시 체크아웃되어 덮어써진다. nginx 설정도 `infra/nginx/icfr.conf` 가 원본이다.
> 예외는 `/etc/icfr/.env` 하나뿐이며, 이 파일만 서버에 존재하고 리포에는 없다.

---

## 1. 최초 배포 (3-2-B 요약)

```bash
# 1) 디스크 마운트
sudo mkfs.ext4 /dev/vdb                     # 최초 1회만
sudo mkdir -p /data && sudo mount /dev/vdb /data
echo '/dev/vdb /data ext4 defaults 0 2' | sudo tee -a /etc/fstab
sudo mkdir -p /data/postgres /data/minio

# 2) docker / compose plugin 설치 후
sudo mkdir -p /etc/icfr
sudo cp .env.prod.example /etc/icfr/.env
sudo chmod 600 /etc/icfr/.env
sudo vi /etc/icfr/.env                      # CHANGE_ME 전부 실값으로

# 3) nginx + 인증서 (80 이 열려 있어야 발급 가능)
sudo apt install -y nginx certbot python3-certbot-nginx
sudo mkdir -p /var/www/certbot
sudo cp infra/nginx/icfr.conf /etc/nginx/sites-available/icfr.conf
sudo ln -sf /etc/nginx/sites-available/icfr.conf /etc/nginx/sites-enabled/icfr.conf
sudo certbot certonly --webroot -w /var/www/certbot -d icfr.synap.co.kr
sudo nginx -t && sudo systemctl reload nginx

# 4) GitHub Actions self-hosted runner 등록 (label: icfr-prod), 리포 루트에서 실행
# 5) 첫 배포는 GitHub Actions 의 Deploy 워크플로를 수동 실행(workflow_dispatch)
```

> ⚠️ `sites-enabled/icfr.conf` 는 심볼릭 링크다. 이 경로로 `sed ... > /etc/nginx/sites-enabled/icfr.conf`
> 같은 리다이렉트를 걸면 셸이 링크를 따라가 **원본(`sites-available/icfr.conf`)을 먼저 비운 뒤** 쓰기 때문에
> 내용이 날아간다. 설정을 고칠 때는 리포의 `infra/nginx/icfr.conf` 를 고쳐 다시 `cp` 한다.

## 2. 일상 배포

`main` 에 머지 → `Deploy` 워크플로 자동 실행 (build → GHCR push → self-hosted runner 에서 up -d → 헬스체크).
**Regina 는 SSH·NCP 콘솔에 접속할 필요가 없다.** 실패 시 Actions 로그에 backend 로그 200줄이 남는다.

## 3. 롤백

되돌릴 커밋 SHA 를 확인한 뒤(Actions 실행 이력 또는 `git log`), 서버에서:

```bash
cd <runner workspace>/claude-icfr        # 예: /home/ubuntu/actions-runner/_work/claude-icfr/claude-icfr
export COMPOSE_PROJECT_NAME=icfr
export IMAGE_TAG=<되돌릴 커밋 SHA>
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
curl -fsS http://127.0.0.1:8000/api/health/
```

- DB 마이그레이션이 포함된 배포를 되돌릴 때는 **이미지만 되돌린다고 스키마가 되돌아가지 않는다.**
  구버전 컨테이너가 신 스키마에서 뜨지 않으면 `docker compose exec backend alembic downgrade <revision>` 을
  수행하되, 그 전에 반드시 4번의 백업을 먼저 뜬다.
- 롤백 후에는 리포에서도 해당 커밋을 revert 해 둔다(다음 push 가 다시 불량 버전을 올리지 않도록).

## 4. 백업 / 복구

```bash
# 백업 (매일 cron 권장)
TS=$(date +%Y%m%d-%H%M)
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > /data/backup/icfr-$TS.sql.gz
# Object Storage 업로드 (NCP Object Storage, s3 호환)
aws s3 cp /data/backup/icfr-$TS.sql.gz s3://<버킷>/icfr/ --endpoint-url <엔드포인트>

# 증빙 파일(MinIO) 백업
tar czf /data/backup/minio-$TS.tar.gz -C /data minio
```

```bash
# 복구
gunzip -c icfr-<TS>.sql.gz | docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

> ⚠️ **`docker compose down -v` 금지** (ADR-0023). 과거 이 명령으로 Excel 업로드 95통제가 소실됐다.
> 컨테이너를 내려야 할 때는 `down` 까지만 쓴다. 데이터는 `/data` 바인드 마운트에 있어
> 컨테이너 재생성으로는 지워지지 않지만, 볼륨 삭제 옵션은 습관적으로도 쓰지 않는다.

## 5. 장애 시 확인 순서

1. **컨테이너 상태** — `docker compose -f docker-compose.prod.yml ps` (Up (healthy) 인지)
2. **로그** — `docker compose -f docker-compose.prod.yml logs --tail=200 backend`
   (기동 시 `alembic upgrade head` 가 먼저 돈다 → 마이그레이션 실패면 여기서 멈춘다)
3. **내부 헬스** — `curl http://127.0.0.1:8000/api/health/` → `/api/health/db` → `/api/health/storage`
4. **nginx** — `sudo nginx -t`, `systemctl status nginx`, `/var/log/nginx/icfr.error.log`
   (502 면 컨테이너가 죽은 것, 413 이면 업로드 크기 초과)
5. **인증서 만료** — `sudo certbot certificates` / 갱신 `sudo certbot renew --dry-run`
6. **디스크** — `df -h /data` (postgres 는 디스크가 차면 쓰기 거부)

## 6. 알려진 후속 과제

- `minio/minio:latest` 는 재현성을 위해 특정 RELEASE 태그로 고정하는 편이 낫다(현재는 로컬 compose 와 동일 유지).
- `MINIO_PUBLIC_ENDPOINT` 는 presigned URL 을 브라우저에 노출할 경우 nginx 경유 경로로 바꿔야 한다.
