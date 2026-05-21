from app.seeds._shared import SeedContext, get_or_create


def seed(ctx: SeedContext) -> None:
    """tester / reviewer 계정 + UserRole 생성. admin은 bootstrap에서 생성됨."""

    # 1. tester 계정 생성 (직접 DB 삽입 — User 생성 API는 Phase 1에 추가 예정)
    #    Phase 0에서는 users 목록 조회 후 없으면 seeds/bootstrap 패턴으로 직접 생성
    from app.core.database import SessionLocal
    from app.core.security import hash_password
    from app.models.user import User

    db = SessionLocal()
    try:
        for email, display_name, role in [
            ("tester@acme.example", "Tester User", "tester"),
            ("reviewer@acme.example", "Reviewer User", "reviewer"),
        ]:
            existing = db.query(User).filter(User.email == email, User.is_deleted == False).first()  # noqa: E712
            if existing:
                print(f"  [users] {email} exists (skip)")
                ctx.ids[email] = str(existing.id)
            else:
                user = User(
                    email=email,
                    hashed_password=hash_password("acme1234"),
                    display_name=display_name,
                    role=role,
                    is_active=True,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                ctx.ids[email] = str(user.id)
                print(f"  [users] {email} created")
    finally:
        db.close()

    # 2. admin ID 취득
    users_resp = ctx.get("/api/users/", params={"limit": 100})
    for u in users_resp.get("items", []):
        ctx.ids.setdefault(u["email"], u["id"])

    # 3. UserRole 등록
    tester_id = ctx.ids.get("tester@acme.example")
    reviewer_id = ctx.ids.get("reviewer@acme.example")
    admin_id = ctx.ids.get("admin@acme.example")

    for user_id, role_name in [
        (tester_id, "Tester"),
        (reviewer_id, "Reviewer"),
        (admin_id, "Administrator"),
    ]:
        if not user_id:
            continue
        get_or_create(
            ctx,
            list_path="/api/users/roles/list",
            create_path="/api/users/roles",
            lookup_key="role_name",
            lookup_value=role_name,
            payload={"user_id": user_id, "role_name": role_name},
        )
