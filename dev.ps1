# dev.ps1 — ICFR 개발 환경 편의 명령
# 사용법: .\dev.ps1 <command>

param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

function Show-Help {
    Write-Host ""
    Write-Host "ICFR 개발 환경 편의 명령" -ForegroundColor Cyan
    Write-Host "================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "사용법: .\dev.ps1 <command>"
    Write-Host ""
    Write-Host "명령:" -ForegroundColor Yellow
    Write-Host "  up        모든 컨테이너 시작 (백그라운드)"
    Write-Host "  down      모든 컨테이너 종료"
    Write-Host "  restart   모든 컨테이너 재시작"
    Write-Host "  logs      모든 컨테이너 로그 (실시간)"
    Write-Host "  ps        컨테이너 상태 확인"
    Write-Host "  clean     컨테이너 + 볼륨 삭제 (데이터 손실 주의)"
    Write-Host "  shell-db  PostgreSQL 콘솔 진입"
    Write-Host "  minio     MinIO 콘솔 URL 출력 (http://localhost:9001)"
    Write-Host "  help      이 도움말"
    Write-Host ""
}

switch ($Command) {
    "up" {
        Write-Host "컨테이너 시작 중..." -ForegroundColor Green
        docker compose up -d
    }
    "down" {
        Write-Host "컨테이너 종료 중..." -ForegroundColor Yellow
        docker compose down
    }
    "restart" {
        Write-Host "컨테이너 재시작 중..." -ForegroundColor Yellow
        docker compose restart
    }
    "logs" {
        docker compose logs -f
    }
    "ps" {
        docker compose ps
    }
    "clean" {
        Write-Host "컨테이너와 볼륨을 모두 삭제합니다. 데이터가 사라집니다." -ForegroundColor Red
        $confirm = Read-Host "정말 진행할까요? (yes/no)"
        if ($confirm -eq "yes") {
            docker compose down -v
            Write-Host "삭제 완료" -ForegroundColor Green
        } else {
            Write-Host "취소됨" -ForegroundColor Yellow
        }
    }
    "shell-db" {
        docker compose exec postgres psql -U icfr_user -d icfr_db
    }
    "minio" {
        Write-Host "MinIO 콘솔: http://localhost:9001" -ForegroundColor Cyan
        Write-Host "사용자: minioadmin (또는 .env의 MINIO_ROOT_USER)"
        Write-Host "비밀번호: .env의 MINIO_ROOT_PASSWORD 참조"
    }
    "seed" {
        Write-Host "시드 데이터 생성 중..." -ForegroundColor Green
        docker compose exec backend python -m app.seeds.run_all
    }
    "test" {
        Write-Host "pytest 실행 중..." -ForegroundColor Green
        docker compose exec backend python -m pytest tests/ -v
    }
    default {
        Show-Help
    }
}
