from app.seeds._shared import SeedContext, get_or_create


def seed(ctx: SeedContext) -> None:
    """Process, RiskCategory, Control, ControlAssertion 시드 데이터."""

    # Process
    process = get_or_create(
        ctx,
        list_path="/api/rcm/processes",
        create_path="/api/rcm/processes",
        lookup_key="code",
        lookup_value="P-SALES",
        payload={"code": "P-SALES", "name": "매출 프로세스", "description": "Order-to-Cash 매출 관련 프로세스"},
    )
    ctx.ids["process_sales"] = process["id"]

    # Risk Categories
    for code, name, desc in [
        ("E", "Existence", "자산·부채·거래의 실재성"),
        ("C", "Completeness", "모든 거래의 완전한 기록"),
        ("V", "Valuation", "적절한 금액으로 측정·표시"),
    ]:
        rc = get_or_create(
            ctx,
            list_path="/api/rcm/risk-categories",
            create_path="/api/rcm/risk-categories",
            lookup_key="code",
            lookup_value=code,
            payload={"code": code, "name": name, "description": desc},
        )
        ctx.ids[f"rc_{code}"] = rc["id"]

    # Controls
    for ctl_code, ctl_name in [
        ("C-001", "매출 인식 검토 통제"),
        ("C-002", "매출 마감 통제"),
    ]:
        ctl = get_or_create(
            ctx,
            list_path="/api/rcm/controls",
            create_path="/api/rcm/controls",
            lookup_key="code",
            lookup_value=ctl_code,
            payload={
                "code": ctl_code,
                "name": ctl_name,
                "process_id": ctx.ids["process_sales"],
                "frequency": "monthly",
            },
        )
        ctx.ids[f"control_{ctl_code}"] = ctl["id"]

    # Control Assertions: C-001 ↔ E, C-001 ↔ C, C-002 ↔ V
    existing_ca = ctx.get("/api/rcm/control-assertions")
    existing_pairs = {
        (ca["control_id"], ca["risk_category_id"])
        for ca in existing_ca.get("items", [])
    }

    for ctl_key, rc_key in [
        ("control_C-001", "rc_E"),
        ("control_C-001", "rc_C"),
        ("control_C-002", "rc_V"),
    ]:
        ctl_id = ctx.ids[ctl_key]
        rc_id = ctx.ids[rc_key]
        if (ctl_id, rc_id) in existing_pairs:
            print(f"  [control-assertions] {ctl_key}↔{rc_key} exists (skip)")
            continue
        ctx.post("/api/rcm/control-assertions", {"control_id": ctl_id, "risk_category_id": rc_id})
        print(f"  [control-assertions] {ctl_key}↔{rc_key} created")
