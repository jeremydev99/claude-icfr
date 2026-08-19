# ADR-0028 (2026-08-12) — ICFR 운영 인프라 최종 기준 확정

> 저장 위치: `docs/adr/ADR-0028_icfr_infra_baseline_20260812.md`
> 관련: ADR-0012(MinIO), ADR-0014(배포 단계화), ADR-0023(데이터 복구 정책), ADR-0025·0026(멀티테넌시), userPreferences 7·8

---

## 1. 배경

지금까지 백엔드·프론트엔드 모두 각자 로컬에서 개발했다. baseline/overlay 전환이 끝나 통제 계층 읽기·쓰기 전 경로가 통일된 시점(pytest 128 passed)에서, 공유 백엔드가 없으면 다음 두 가지가 계속 반복된다.

- Regina 로컬 DB와 마스터 로컬 DB의 상태 불일치 (baseline 0행 사건의 근본 원인)
- 프론트가 실제 API 대신 mock을 쓰는 상황을 늦게 발견

동시에 본 시스템은 **외부 고객사에 판매할 제품**이다(섹션 20). 따라서 이번 서버는 "개발 편의용 임시 서버"가 아니라 **최종 판매 기준 아키텍처의 축소판**으로 만든다. 지금 구조를 잡아두지 않으면 고객사 납품 시점에 전면 retrofit이 발생한다.

**기존 자산**: 동일 NCP 계정에 hrpms(인사시스템) 운영 서버가 이미 존재한다. ICFR은 hrpms와 **네트워크·계정·키 전부 분리**한다.

| 항목 | hrpms (기존, 실측) | ICFR (신규) |
|---|---|---|
| VPC | `hrpms-prod-vpc` / `10.1.0.0/16` | `icfr-prod-vpc` / `10.2.0.0/16` |
| Subnet | `hrpms-prod-subnet` / `10.1.1.0/24` / KR-1 | `10.2.1.0/24`(Public) + `10.2.2.0/24`(Private) / KR-1 |
| 서버 | `hrpms-prod-server` s2-g3a (2vCPU·8GB), KVM·G3 | 동일 스펙 |
| 서버 이미지 | ubuntu-24.04-base | 동일 |
| 기본 스토리지 | CB1 50GB, **암호화 N** | CB1 50GB, **암호화 Y** |
| 반납 보호 | **해제** | **설정** |
| 인증키 | `hrpms-prod-key` | `icfr-prod-key` (별도 발급) |

> hrpms 서버의 암호화 N·반납 보호 해제는 별건으로 검토 필요. 반납 보호는 즉시 설정 가능하나 스토리지 암호화는 생성 시점에만 지정 가능하므로 hrpms는 재생성 없이는 변경 불가.

---

## 2. 결정

### 2.1 네트워크

- ICFR 전용 **별도 VPC**로 격리한다. hrpms VPC와 **피어링하지 않는다**. 두 시스템 간 통신 요건이 발생하면 그때 ADR로 별도 결정한다.
- VPC CIDR은 생성 후 수정 불가하므로 `10.2.0.0/16`으로 확정한다. hrpms(`10.1.0.0/16`)와 충돌 없음.
- 서브넷을 **처음부터 2개** 만든다.
  - `icfr-prod-pub-subnet` `10.2.1.0/24` — Public, 애플리케이션 서버
  - `icfr-prod-priv-subnet` `10.2.2.0/24` — Private, **Phase 2 Cloud DB for PostgreSQL 이관 대비 예약**
  - 지금 Private 서브넷을 만들어두는 이유: 나중에 만들면 DB 이관 시 네트워크 재구성이 필요하다. 비용은 0원이다.
- ACG(`icfr-prod-acg`) 인바운드 최소 개방:

| 프로토콜 | 포트 | 접근 소스 | 용도 |
|---|---|---|---|
| TCP | 443 | 사무실 고정 IP `/32` | 애플리케이션(HTTPS) |
| TCP | 80 | `0.0.0.0/0` | Let's Encrypt HTTP-01 챌린지 전용 (아래 2.6 참조) |
| TCP | 22 | 사무실 고정 IP `/32` | 긴급 운영 (상시 사용 아님) |

- **인바운드 22를 GitHub Actions에 열지 않는다.** Actions runner의 출발지 IP 대역이 지나치게 넓어 최소 권한 원칙이 무너진다. 대신 self-hosted runner를 쓴다(2.4).
- 아웃바운드는 전체 허용.
- 모든 ICFR 리소스에 태그 `service=icfr`를 붙인다. Sub Account ABAC 정책의 판별 근거로 쓴다(문자열 이름 매칭 금지 — 회귀 방지 원칙 1).

### 2.2 서버

- `icfr-prod-server`, s2-g3a(2vCPU·8GB), KVM·G3, ubuntu-24.04-base.
- **기본 스토리지 암호화 = Y** (생성 시점에만 지정 가능. 판매 제품의 필수 요건).
- 생성 직후 **반납 보호 설정**.
- 인증키는 `icfr-prod-key`를 신규 발급한다. hrpms 키를 재사용하지 않는다 — 키 하나가 유출되면 두 시스템이 동시에 뚫린다.
- 요금제: **시간 요금제**. 스펙 변경 가능성이 남아 있는 동안 월 요금제는 스케일업 시 중복 과금이 발생한다.
- 서버에서 **소스를 빌드하지 않는다.** 컨테이너 이미지 pull만 수행한다(2.4).

### 2.3 스토리지 / 데이터 배치

- OS 기본 디스크(50GB)와 **데이터 디스크를 분리**한다. 추가 Block Storage 100GB를 `/dev/vdb` → `/data`로 마운트(`/etc/fstab` 등록).
- 배치:
  - `/data/postgres` — PostgreSQL 데이터 볼륨
  - `/data/minio` — MinIO 오브젝트
  - `/data/backup` — 백업 임시 산출물
- 이유: 서버를 재생성하거나 스펙을 바꿔도 데이터 디스크를 분리 후 재연결하면 데이터가 보존된다. 또한 Phase 2에 Cloud DB로 이관할 때 `/data/postgres`만 덤프 대상으로 격리된다.
- **`docker compose down -v` 금지**(ADR-0023). 운영 서버에서는 배포 스크립트에 해당 명령이 들어갈 수 없다.

### 2.4 배포 파이프라인

사람이 서버에 접속해 배포하지 않는다. 배포 주체는 CI다.

```
개발자(마스터/Regina): 브랜치 push → PR → main 머지
  → GitHub Actions: backend/frontend 이미지 빌드
  → GHCR push (태그 = 커밋 SHA, latest 태그 사용 금지)
  → self-hosted runner(ICFR 서버 내부)가 docker compose pull && up -d
```

- **이미지 태그는 커밋 SHA 고정.** `latest`는 "지금 서버에 뭐가 떠 있는지"를 알 수 없게 만든다. 내부통제 시스템의 배포 이력이 추적 불가하면 자기모순이다.
- **롤백 = 이전 SHA 태그로 재기동.** 절차를 README에 명문화한다.
- **self-hosted runner를 ICFR 서버에 설치**한다. runner가 GitHub로 아웃바운드 연결을 맺으므로 인바운드 22 개방이 불필요하다. 배포 이력은 Actions 로그에 남는다.
- Regina에게 필요한 권한은 **GitHub repo write뿐**이다. NCP 콘솔 권한도, SSH 키도 필요 없다.
- 프론트엔드는 같은 서버 nginx가 정적 빌드를 서빙한다. 설치형(On-Premise) 판매 구성과 동일해 배포 분기가 생기지 않는다.

### 2.5 시크릿 관리

- **단일 원천은 GitHub Secrets**로 둔다. 서버의 `.env`는 그 사본이다.
- 서버 배치: `/etc/icfr/.env`, 소유자 `root`, 권한 `600`. 리포지토리 디렉터리 밖에 둔다(git 실수 커밋 원천 차단).
- Public 레포이므로 실 계정·토큰·비밀번호는 어떤 경로로도 커밋 금지(섹션 7.1).
- 최소 교체 대상: PostgreSQL 비밀번호, MinIO 액세스 키, JWT 시크릿 — 로컬 개발값을 운영에 재사용하지 않는다.
- Phase 2에 NCP Secret Manager 도입을 검토한다.

### 2.6 도메인 / TLS

- `icfr-api.<사이냅소프트 도메인>` → ICFR 서버 공인 IP (A 레코드).
- nginx + Let's Encrypt(certbot), 자동 갱신.
- **80 포트를 전체 개방하되 nginx는 `/.well-known/acme-challenge/`만 서빙하고 나머지 전 경로를 443으로 리다이렉트**한다. HTTP-01 챌린지는 전 세계에서 접근 가능해야 성립하므로 사무실 IP만 열면 인증서 발급·갱신이 실패한다. 애플리케이션 자체는 443에서 사무실 IP로 제한되므로 노출면은 챌린지 경로뿐이다.
- HTTP 헤더: HSTS, X-Content-Type-Options, X-Frame-Options 적용.

### 2.7 계정 / 권한

| 주체 | 권한 | 근거 |
|---|---|---|
| 메인 계정 | 인프라 생성·변경 전권 | Access Key 발급하지 않음 |
| `icfr-deploy` (서버 OS 계정) | self-hosted runner 실행 전용, sudo 제한 | 배포 자동화 |
| `icfr-regina` (Sub Account) | 사용자 정의 정책 `icfr-view-only` — 태그 `service=icfr` 리소스에 대한 **View만**, Change 없음, Access Key 미발급 | 서버 가동 상태 확인용. 배포는 GitHub 경로로 수행하므로 Change 불필요 |

- hrpms 리소스는 태그가 다르므로 정책상 자동 배제된다. 이름 문자열이 아니라 태그(구조)로 판별한다.

### 2.8 백업 / 복구 (ADR-0023 연장)

- `pg_dump | gzip` 일 1회(cron, 새벽) → `/data/backup` → Object Storage 업로드.
- MinIO 버킷은 주 1회 동기화.
- 보존 30일, 이후 자동 삭제. → **2026-08-19 변경: 보존 90일.**
  사유: 실측 백업 크기 34,918바이트 기반 재산정 — 90일 보존해도 Object Storage 월 요금이
  0.1원 미만이라 비용이 사실상 0이고, 감사 대응(과거 시점 복원 요구) 여지를 넓히는 편이 이득이다.
  (원 결정 30일은 취소선 없이 이력으로 남긴다. 운영 반영값은 `/etc/icfr/.env` 의 `BACKUP_RETENTION_DAYS=90`.)
- **복구 절차를 문서로 남기고, 월 1회 실제 복구 리허설을 수행한다.** 검증하지 않은 백업은 백업이 아니다.
- 회계법인 PoC 시연 전에는 반드시 직전 백업 존재를 확인한다.

### 2.9 모니터링

- NCP Cloud Insight 기본 메트릭(CPU·메모리·디스크) + 임계치 알림.
- Docker healthcheck를 backend·postgres·minio 각 서비스에 정의.
- Phase 1.5에 잔디 Webhook 알림 연동(기술스택에 httpx 기 채택).

### 2.10 Phase 2 확장 트리거 (지금 하지 않는 것과 그 조건)

| 항목 | 이번 범위 | 전환 조건 |
|---|---|---|
| Cloud DB for PostgreSQL | 컨테이너 postgres | 고객사 실데이터 투입 또는 동시 사용자 50명 초과 |
| Load Balancer + 다중 존 | 단일 서버·단일 존 | 회계법인 SaaS 상용 서비스 개시 |
| Kubernetes | Docker Compose (ADR-0014) | 테넌트 10개 초과 |
| Celery + Redis (ADR-0013) | BackgroundTasks | 보고서 대량 생성·정기 스케줄 요건 발생 |
| Secret Manager | `/etc/icfr/.env` | 운영 인원 3명 초과 |

---

## 3. 실행 순서

### 3-1. NCP 콘솔 작업 (마스터 수동)

1. VPC 생성 — `icfr-prod-vpc` / `10.2.0.0/16`
2. Subnet 생성 — `icfr-prod-pub-subnet` `10.2.1.0/24`(Public, KR-1), `icfr-prod-priv-subnet` `10.2.2.0/24`(Private, KR-1)
3. 인증키 생성 — `icfr-prod-key` (pem 안전 보관)
4. ACG 생성 — `icfr-prod-acg`, 인바운드 규칙 2.1 표대로
5. 서버 생성 — `icfr-prod-server`, s2-g3a, ubuntu-24.04-base, **스토리지 암호화 Y**, 시간 요금제
6. 서버 생성 직후 — **반납 보호 설정**
7. 공인 IP 신청·연결
8. Block Storage 100GB 생성·연결
9. Object Storage 버킷 생성 — `icfr-backup`
10. 전 리소스에 태그 `service=icfr` 부여
11. Sub Account 정책 `icfr-view-only` 생성 → `icfr-regina` 계정 생성·부여
12. DNS A 레코드 등록 — `icfr-api.<도메인>` → 공인 IP

### 3-2. 서버 초기 설정 + 배포 (Claude Code 프롬프트로 별도 작성)

13. OS 업데이트, `/data` 마운트 + fstab
14. Docker·Docker Compose 설치
15. `/etc/icfr/.env` 배치
16. GHCR 인증, self-hosted runner 설치·등록
17. nginx + certbot, TLS 발급
18. `docker compose up -d` → Alembic 마이그레이션 → `seed_baseline.py --reset`
19. **검증**: baseline_controls 93행을 psql로 직접 확인 (스크립트 출력 신뢰 금지)
20. 백업 cron 등록 + **1회 복구 리허설**
21. Regina 온보딩 — API 엔드포인트 전달, 프론트 `.env` 전환, mock 제거 확인

---

## 4. 기각한 대안

| 대안 | 기각 사유 |
|---|---|
| hrpms VPC에 서버만 추가 | 격리 실패. 한쪽 침해가 다른 쪽으로 전이. 인사데이터와 회계내부통제데이터를 같은 네트워크에 두는 것은 판매 시 결격 사유 |
| 서버에서 `git pull && docker build` | 빌드 재현성 없음. 고객사 서버에서 소스 빌드 불가. 판매 기준 미달 |
| GitHub Actions에서 SSH 직접 배포 | 인바운드 22를 광범위 IP 대역에 개방해야 함 |
| `latest` 태그 배포 | 현재 배포 버전 추적 불가, 롤백 경로 부재 |
| Regina에게 Change 권한 부여 | 배포는 GitHub 경로로 수행되므로 불필요. 최소 권한 위배 |
| watchtower 자동 폴링 배포 | 배포 이력 추적 약함. SHA 태그 고정 배포와 상충 (**폴백**: self-hosted runner 설치가 막힐 경우에만 재검토) |
| 처음부터 Cloud DB + LB 이중화 | 현 규모 대비 과투자. 단 이관 경로(Private 서브넷)는 지금 확보 |

---

## 5. 회귀 가드

- hrpms 서버·VPC·ACG는 **일체 건드리지 않는다.** 본 작업 중 hrpms 리소스 변경이 발생하면 즉시 중단.
- VPC CIDR·스토리지 암호화 여부는 **생성 후 변경 불가**. 5·1단계 실행 전 값을 재확인한다.
- seed 실행 후 검증은 스크립트 출력이 아니라 psql 직접 조회로 한다(2026-08-11 검증 선례).
- `docker compose down -v`는 운영 서버 어떤 스크립트에도 포함하지 않는다.

---

## 6. 확인 필요 (실행 전 채울 값)

- [ ] 사이냅소프트 도메인 정확한 FQDN
- [ ] 사무실 고정 공인 IP (`x.x.x.x/32`)
- [ ] hrpms 서버 월 청구액 (NCP 콘솔 > 이용 내역) — ICFR 예상 비용의 1차 출처
