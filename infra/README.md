# 인프라 사용 안내

ICFR 시스템의 개발 환경 셋업 가이드.

## 필수 도구

| 도구 | 용도 | 설치 링크 |
|---|---|---|
| Docker Desktop | 컨테이너 실행 | https://www.docker.com/products/docker-desktop |
| Git | 코드 동기화 | https://git-scm.com/ |
| Python 3.12+ | 백엔드 개발 (TrustBuilder) | https://www.python.org/ |
| Node.js 20+ | 프론트엔드 개발 (Regina) | https://nodejs.org/ |

Windows 10/11에서는 Docker Desktop 사용 시 **WSL2 활성화**가 필요할 수 있음.

## 첫 셋업 (한 번만)

```powershell
# 1. 레포 클론 (이미 했다면 생략)
git clone https://github.com/jeremydev99/claude-icfr.git
cd claude-icfr

# 2. 환경 변수 파일 복사
copy .env.example .env

# 3. .env 파일 열어서 비밀번호·시크릿 변경 (운영 시)
# 개발 환경에서는 기본값 그대로 OK

# 4. 컨테이너 시작
.\dev.ps1 up

# 5. 컨테이너 상태 확인
.\dev.ps1 ps
```

## 일상 명령

| 작업 | 명령 |
|---|---|
| 컨테이너 시작 | `.\dev.ps1 up` |
| 컨테이너 종료 | `.\dev.ps1 down` |
| 로그 보기 | `.\dev.ps1 logs` |
| 상태 확인 | `.\dev.ps1 ps` |
| DB 콘솔 | `.\dev.ps1 shell-db` |
| MinIO 콘솔 정보 | `.\dev.ps1 minio` |

## 서비스 접속

- **FastAPI**: http://localhost:8000 (작업 단위 2 이후)
- **PostgreSQL**: localhost:5432 (외부 DB 도구로 접속)
- **MinIO API**: http://localhost:9000
- **MinIO 콘솔**: http://localhost:9001

## 트러블슈팅

### Q: 포트 충돌 (5432, 9000 등이 이미 사용 중)
A: `.env`에서 포트 변경 또는 기존 서비스 종료. `docker-compose.yml`의 ports도 함께 변경.

### Q: Docker Desktop이 시작되지 않음
A: Windows 기능에서 "WSL2" 활성화. 재부팅 필요.

### Q: 컨테이너 로그에 권한 오류
A: `.\dev.ps1 clean` 후 `.\dev.ps1 up` 다시 실행. 볼륨 권한 초기화됨.

### Q: PostgreSQL 데이터를 완전히 리셋하고 싶음
A: `.\dev.ps1 clean` 실행. 모든 컨테이너·볼륨 삭제 후 다시 시작.

## 백업·복구 (Phase 2 이후 추가 예정)

운영 환경 진입 시 추가 예정.
