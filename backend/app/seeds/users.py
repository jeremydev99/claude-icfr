"""개발·테스트용 계정 + 테넌트 역할 시드. **로컬 전용** (`dev.ps1 seed` → `run_all`).

**운영은 이 경로를 타지 않는다.** 운영의 첫 역할 1행은 마스터가 SQL 로 넣는다
(`ClaudeICFR.md` §8.5). 여기서는 **그 절차를 로컬에서 그대로 재현**한다 —
`sys_admin` 1행만 직접 삽입하고, 나머지는 API 로 배정한다. 절차가 실제로 도는지를
개발 환경에서 매번 확인하게 되는 효과가 있다.

**구 3역할(`Administrator`/`Reviewer`/`Tester`)을 더 만들지 않는다**(13.9-24).
그 값들은 ADR-0031 5역할이 아니라 어떤 판정에도 걸리지 않으며, 13.9-35 값 검증
이후로는 **API 로 배정 자체가 되지 않는다**(422). 어느 층 의미였는지 문서 근거가
없으므로 1:1 매핑을 만들지 않고, **개발·테스트에 필요한 조합**으로 다시 짰다.

| 계정 | `users.role` | 테넌트 역할 | 왜 필요한가 |
|---|---|---|---|
| `admin@acme.example` | `admin` | `sys_admin` | 부트스트랩 1행. 이게 없으면 아무도 역할을 배정할 수 없다 |
| `icfrmgr@acme.example` | `user` | `icfr_manager` | 역할 배정·정책 변경 주체. 시스템 관리 계정과 분리한다(ADR-0031 §2.1.1) |
| `extaudit@acme.example` | `user` | `external_auditor` | `can_write=false` 경로 확인용. FE 쓰기 차단 작업에 필요하다 |
| `tester@acme.example` | `tester` | — | 역할 없는 일반 사용자(= `can_write=true` 기본 경로) |
| `reviewer@acme.example` | `reviewer` | — | 〃 |

`ceo`·`auditor` 는 시드하지 않는다 — **현재 어떤 판정도 이 두 값에 의존하지 않아**
계정을 만들어도 확인할 동작이 없다. 필요해지는 시점에 추가한다.

기존 로컬 DB 에 남아 있는 구 3행은 이 시드가 지우지 않는다(추가만 한다). 정리하려면:

    DELETE FROM user_roles WHERE role_name IN ('Administrator', 'Reviewer', 'Tester');
"""
from app.core.audit_context import SYSTEM_SEED_USERS, system_actor
from app.models.role_assignment import (
    ROLE_EXTERNAL_AUDITOR,
    ROLE_ICFR_MANAGER,
    ROLE_SYS_ADMIN,
)
from app.seeds._shared import SeedContext

# 값은 `models/role_assignment.py` 상수를 참조한다 — 문자열 리터럴을 쓰면 겸직 판정과
# 배정 검증이 보는 목록과 어긋날 수 있고, 어긋난 것을 알 방법이 없다.
ADMIN_EMAIL = "admin@acme.example"
ICFR_MANAGER_EMAIL = "icfrmgr@acme.example"
EXTERNAL_AUDITOR_EMAIL = "extaudit@acme.example"
SEED_PASSWORD = "acme1234"

# (email, display_name, users.role) — `users.role` 은 시스템 관리 축이며
# 테넌트 역할과 서로 참조하지 않는다(ADR-0031 §3.2).
SEED_USERS = [
    ("tester@acme.example", "Tester User", "tester"),
    ("reviewer@acme.example", "Reviewer User", "reviewer"),
    (ICFR_MANAGER_EMAIL, "내부회계관리자", "user"),
    (EXTERNAL_AUDITOR_EMAIL, "외부감사인", "user"),
]


@system_actor(SYSTEM_SEED_USERS)
def _ensure_users(ctx: SeedContext) -> None:
    """계정 + 테넌트 접근 권한을 직접 삽입한다(User 생성 API 는 admin 전용이라 순서가 꼬인다).

    **테넌트 접근이 없으면 로그인은 되지만 모든 요청이 403 이다**(`core/deps`).
    개정 전에는 이 행을 만들지 않아 시드 계정으로 API 를 호출할 수 없었다.
    """
    from app.core.database import SessionLocal
    from app.core.security import hash_password
    from app.core.tenant_context import DEFAULT_TENANT_ID
    from app.models.tenant import UserTenantAccess
    from app.models.user import User

    db = SessionLocal()
    try:
        for email, display_name, role in SEED_USERS:
            user = db.query(User).filter(
                User.email == email, User.is_deleted == False,  # noqa: E712
            ).first()
            if user is None:
                user = User(
                    email=email,
                    hashed_password=hash_password(SEED_PASSWORD),
                    display_name=display_name,
                    role=role,
                    is_active=True,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                print(f"  [users] {email} created")
            else:
                print(f"  [users] {email} exists (skip)")
            ctx.ids[email] = str(user.id)

            access = db.query(UserTenantAccess).filter(
                UserTenantAccess.user_id == user.id,
                UserTenantAccess.tenant_id == DEFAULT_TENANT_ID,
                UserTenantAccess.is_deleted == False,  # noqa: E712
            ).first()
            if access is None:
                db.add(UserTenantAccess(
                    user_id=user.id, tenant_id=DEFAULT_TENANT_ID, role=role,
                ))
                db.commit()
                print(f"  [users] {email} tenant access granted")
    finally:
        db.close()


@system_actor(SYSTEM_SEED_USERS)
def _ensure_bootstrap_sys_admin(admin_id: str) -> None:
    """admin 에게 `sys_admin` 1행을 **직접 삽입**한다 — §8.5 부트스트랩의 로컬 재현.

    **API 로는 만들 수 없다.** `require_role_assigner` 가 `icfr_manager`(또는
    `icfr_manager` 0명일 때 `sys_admin`)를 요구하는데, 새 환경의 `user_roles` 는
    비어 있어 **둘 다 없기 때문이다**(13.9-35). `users.role == "admin"` 을 보고
    열어 주면 ADR-0031 §3.2 가 금지한 추론이 되므로 그렇게 하지 않는다.

    **이 함수는 시드(로컬) 전용이다.** 운영에서는 마스터가 SQL 로 같은 1행을 넣는다 —
    `bootstrap_admin`(앱 기동 시 실행, 운영 포함)에 넣지 않는 이유가 이것이다.
    거기에 넣으면 모든 환경이 자동으로 `sys_admin` 을 갖게 되어 §8.5 절차가 무의미해지고,
    §3.2 경계도 함께 무너진다.
    """
    from uuid import UUID

    from app.core.database import SessionLocal
    from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
    from app.models.user_mgmt import UserRole

    db = SessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        existing = db.query(UserRole).filter(
            UserRole.user_id == UUID(admin_id),
            UserRole.role_name == ROLE_SYS_ADMIN,
            UserRole.is_deleted == False,  # noqa: E712
        ).first()
        if existing is not None:
            print(f"  [roles] {ROLE_SYS_ADMIN} exists (skip)")
            return
        db.add(UserRole(user_id=UUID(admin_id), role_name=ROLE_SYS_ADMIN))
        db.commit()
        print(f"  [roles] {ROLE_SYS_ADMIN} created (부트스트랩 1행, 직접 삽입)")
    finally:
        reset_active_tenant(tok)
        db.close()


def _assign_role(ctx: SeedContext, user_id: str, role_name: str) -> None:
    """API 로 테넌트 역할을 배정한다. 멱등 — `(user_id, role_name)` 둘 다로 판별한다.

    `_shared.get_or_create` 는 한 키로만 조회해서 "누구의 역할인지"를 구분하지 못한다.
    """
    for item in ctx.get("/api/users/roles/list", params={"limit": 200}).get("items", []):
        if item.get("user_id") == user_id and item.get("role_name") == role_name:
            print(f"  [roles] {role_name} exists (skip)")
            return
    ctx.post("/api/users/roles", {"user_id": user_id, "role_name": role_name})
    print(f"  [roles] {role_name} created")


def seed(ctx: SeedContext) -> None:
    """계정·테넌트 접근·테넌트 역할을 만든다. 호출 시 ctx 는 admin 으로 로그인돼 있다."""
    _ensure_users(ctx)

    # admin id 취득 — bootstrap 이 만든 계정이라 위 목록에 없다
    for u in ctx.get("/api/users/", params={"limit": 100}).get("items", []):
        ctx.ids.setdefault(u["email"], u["id"])
    admin_id = ctx.ids.get(ADMIN_EMAIL)
    if not admin_id:
        raise RuntimeError(f"{ADMIN_EMAIL} 계정을 찾을 수 없다 — bootstrap 이 돌았는지 확인할 것")

    # ① 부트스트랩 1행(직접 삽입) → ② sys_admin 자격으로 첫 icfr_manager 배정(API)
    #    → ③ 그 시점에 부트스트랩 경로는 닫히므로 이후 배정은 icfr_manager 가 한다.
    #    운영에서 밟는 순서와 같다(§8.5). 로컬에서 매번 이 경로가 실제로 도는지 확인된다.
    _ensure_bootstrap_sys_admin(admin_id)
    _assign_role(ctx, ctx.ids[ICFR_MANAGER_EMAIL], ROLE_ICFR_MANAGER)

    ctx.login(ICFR_MANAGER_EMAIL, SEED_PASSWORD)
    _assign_role(ctx, ctx.ids[EXTERNAL_AUDITOR_EMAIL], ROLE_EXTERNAL_AUDITOR)

    # 뒤따르는 시드(rcm·test_module·…)는 admin 자격을 전제한다 — 반드시 되돌린다.
    ctx.login(ADMIN_EMAIL, "admin123")
