"""AI 제안 계기 확인 — 매일 서버 cron 이 실행한다(ADR-0042).

    docker exec icfr-backend python -m app.jobs.ai_daily

회사(tenant)마다 활성 회사를 걸고 계기를 본다. 만든 것이 없으면 아무것도 바꾸지 않는다.
"""
from datetime import date

from app.core.database import SessionLocal
from app.core.tenant_context import reset_active_tenant, set_active_tenant
from app.models.tenant import Tenant
from app.services import ai_schedule


def main() -> None:
    db = SessionLocal()
    try:
        tenants = [t.id for t in db.query(Tenant).filter(Tenant.is_active == True).all()]  # noqa: E712
    finally:
        db.close()
    today = date.today()
    for tid in tenants:
        tok = set_active_tenant(tid)
        db = SessionLocal()
        try:
            prop = ai_schedule.propose_schedule(db, today)
            db.commit()
            print(f"[ai_daily] tenant={tid} schedule={'제안 ' + prop.summary if prop else '없음'}")
        except Exception as e:  # 한 회사가 실패해도 다른 회사는 계속
            db.rollback()
            print(f"[ai_daily] tenant={tid} 실패: {e}")
        finally:
            db.close()
            reset_active_tenant(tok)


if __name__ == "__main__":
    main()
