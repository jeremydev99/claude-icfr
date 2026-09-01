# PROMPT 3-2-A — ICFR 운영 배포 산출물 작성

## 목적

NCP에 생성된 ICFR 운영 서버에 배포하기 위한 산출물을 작성한다.
서버는 이미 준비되어 있고, 이 작업은 **로컬 리포지토리에 파일을 만드는 것까지**다.
서버 접속·실행은 이 프롬프트 범위가 아니다(3-2-B에서 수행).

## 확정된 사실 (조회하지 말고 그대로 사용)

- 도메인: `icfr.synap.co.kr` (A 레코드 → `101.79.21.122`, 전파 확인 완료)
- 서버: Ubuntu 24.04, KVM, 2vCPU/8GB
- 데이터 디스크: `/dev/vdb` 50GB → `/data`에 마운트 예정
- 방화벽(ACG): inbound 22·443은 `58.151.46.178/32`만, 80은 `0.0.0.0/0`
- 컨테이너 레지스트리: GHCR (`ghcr.io/jeremydev99/claude-icfr`)
- 기존 `.github/workflows/ci.yml` 1개 존재
- `backend/Dockerfile`: `CMD ["sh","-c","alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]`
- `frontend/Dockerfile`: 멀티스테이지(node:20-alpine 빌드 → nginx:alpine, EXPOSE 80)
- 루트 `docker-compose.yml`: postgres / minio / backend 3개 서비스, 볼륨 `postgres_data`·`minio_data`, 네트워크 `icfr-network`

## 절대 원칙

1. **기존 `docker-compose.yml`을 수정하지 않는다.** Regina가 매일 쓰는 로컬 개발 파일이다. 운영 설정은 전부 신규 파일로 분리한다.
2. **기존 `ci.yml`을 수정하지 않는다.** 배포는 신규 워크플로 파일로 분리한다.
3. **시크릿 실값을 어떤 파일에도 쓰지 않는다.** Public 레포다. 예시 파일에는 키 이름만 넣는다.
4. **제로 추상화(ADR-0020)** — 불필요한 래퍼 스크립트를 만들지 않는다. 필요한 명령을 직접 쓴다.
5. 추정 금지. 기존 파일의 실제 내용(포트, 환경변수 이름, 서비스명, 헬스체크 엔드포인트)을 **직접 읽어서 확인한 뒤** 그 값에 맞춰 작성한다. 특히 backend가 사용하는 환경변수 이름은 `backend/app/` 설정 파일에서 실제로 확인할 것.

---

## 작성할 산출물

### 1. `docker-compose.prod.yml` (루트)

로컬 compose와의 차이:

| 항목 | 운영 |
|---|---|
| 이미지 | `build:` 대신 `image: ghcr.io/jeremydev99/claude-icfr/backend:${IMAGE_TAG}` (frontend도 동일 패턴) |
| 볼륨 | named volume 대신 bind mount — `/data/postgres`, `/data/minio` |
| 포트 | 호스트 노출은 `127.0.0.1:` 바인딩만. 외부 노출은 호스트 nginx가 담당 |
| 서비스 | postgres / minio / backend / **frontend** (4개) |
| env | `env_file: /etc/icfr/.env` |
| restart | `unless-stopped` |

- 4개 서비스 모두 `healthcheck` 정의.
- backend는 `depends_on`에 postgres·minio의 `condition: service_healthy`.
- **`down -v`가 들어갈 여지를 만들지 말 것**(ADR-0023 / 과거 데이터 손실 사고).

### 2. `infra/nginx/icfr.conf`

호스트에 직접 설치되는 nginx 설정(컨테이너 아님).

- 80 포트: `/.well-known/acme-challenge/`만 서빙, 그 외 전부 443 리다이렉트
- 443 포트: TLS 종료 (Let's Encrypt 인증서 경로)
- `/api/` → `http://127.0.0.1:<backend 포트>` 프록시
- `/` → `http://127.0.0.1:<frontend 포트>` 프록시
- 프록시 헤더: `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`
- 보안 헤더: HSTS, X-Content-Type-Options, X-Frame-Options
- 파일 업로드 대비 `client_max_body_size` 설정 (증빙 파일 업로드 기능 있음 — 기존 백엔드 제한값을 확인해서 맞출 것)

### 3. `.github/workflows/deploy.yml`

트리거: `main` 브랜치 push + `workflow_dispatch`(수동 실행)

Job 1 (`build`, ubuntu-latest):
- backend·frontend 이미지 빌드
- 태그는 **커밋 SHA**. `latest` 태그를 배포에 사용하지 않는다
- GHCR push (`GITHUB_TOKEN` 사용, `packages: write` 권한)

Job 2 (`deploy`, self-hosted runner):
- `needs: build`
- `IMAGE_TAG`에 커밋 SHA를 넣어 `docker compose -f docker-compose.prod.yml pull && up -d`
- **배포 후 헬스체크 검증**: backend 헬스 엔드포인트가 200을 반환할 때까지 폴링(최대 60초). 실패 시 job을 실패로 처리하고 로그 출력
- 오래된 이미지 정리(`docker image prune`)는 하되, 볼륨은 절대 건드리지 않는다

### 4. `.env.prod.example`

`/etc/icfr/.env`에 들어갈 키 목록. **값은 전부 빈 문자열 또는 `CHANGE_ME`**.
`backend/app/` 설정에서 실제 사용하는 환경변수를 확인해서 누락 없이 나열할 것.
각 키 위에 한 줄 주석으로 용도 명시.

### 5. `docs/DEPLOY.md`

- 최초 배포 절차 (3-2-B 요약)
- 일상 배포: main 머지 → 자동. Regina는 SSH·NCP 콘솔 불필요
- **롤백 절차**: 이전 커밋 SHA로 `IMAGE_TAG` 지정 후 재기동하는 구체적 명령
- 백업/복구 절차: `pg_dump` → Object Storage, 복구 시 명령
- 장애 시 확인 순서 (컨테이너 상태 → 로그 → nginx → 인증서 만료)
- **주의**: 서버에서 파일을 직접 수정하지 말 것(다음 배포 시 덮어써짐)

---

## 작업 순서

1. 기존 `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `ci.yml`, backend 설정 파일을 **읽어서 실제 값 확인** (포트·환경변수명·헬스체크 경로·업로드 크기 제한)
2. 위 5개 파일 작성
3. `docker compose -f docker-compose.prod.yml config`로 문법 검증 (실행은 하지 말 것)
4. 작성한 파일 목록과, 기존 파일 중 **수정한 것이 없음**을 확인해서 보고

## 커밋

- 한 커밋으로 묶는다. 메시지: `feat(infra): 운영 배포 산출물 추가 (compose.prod, nginx, deploy workflow, DEPLOY.md)`
- `git add`는 **명시적 경로 지정**으로만 한다. `git add .` 금지
- 커밋 전 `git pull --no-rebase` (Regina가 자주 push함)
- 신규 인프라 파일이므로 push는 **마스터 확인 후**. 커밋까지만 하고 보고할 것

## 보고 형식

- 생성한 파일 경로 목록
- 기존 파일에서 읽어 반영한 실제 값(포트·환경변수명 등)을 표로
- `.env.prod.example`에 나열한 키 목록
- 검증 명령 실행 결과
