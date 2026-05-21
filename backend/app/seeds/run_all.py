"""시드 전체 실행 진입점. 멱등성 보장 — 여러 번 실행해도 안전."""
from app.seeds._shared import SeedContext
from app.seeds import users, rcm, test_module, remediation, evidence


def main() -> None:
    ctx = SeedContext(base_url="http://localhost:8000")
    ctx.login("admin@acme.example", "admin123")
    print("✓ admin 로그인 완료\n")

    print("[1/5] Seeding users...")
    users.seed(ctx)

    print("\n[2/5] Seeding RCM...")
    rcm.seed(ctx)

    print("\n[3/5] Seeding test runs...")
    test_module.seed(ctx)

    print("\n[4/5] Seeding remediation...")
    remediation.seed(ctx)

    print("\n[5/5] Seeding evidence...")
    evidence.seed(ctx)

    print("\n✓ All seeds complete")


if __name__ == "__main__":
    main()
