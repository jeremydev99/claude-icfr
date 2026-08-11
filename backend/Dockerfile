FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


FROM python:3.12-slim

WORKDIR /app

# 빌더에서 설치된 패키지 복사
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# 앱 코드 복사
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY tests/ ./tests/
# seeds/ = 엑셀 단일 원천 + baseline 시드 스크립트, scripts/ = 1회성 이관 스크립트.
# 둘 다 기동 시 자동 실행되지 않고 마스터가 exec 로 명시 실행한다.
COPY seeds/ ./seeds/
COPY scripts/ ./scripts/

EXPOSE 8000

# 시작 시 마이그레이션 후 uvicorn 실행
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
