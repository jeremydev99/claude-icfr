from app.seeds._shared import SeedContext, get_or_create

# 메인 컨트롤 키 — test_module.py, evidence.py 와 공유
MAIN_CONTROL_KEY = "control_P-SALES-010-10-10"


def seed(ctx: SeedContext) -> None:
    """Process → SubProcess → Risk → Control 계층 시드 (Phase 1 구조)."""

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

    # SubProcess
    sp = get_or_create(
        ctx,
        list_path="/api/rcm/sub-processes",
        create_path="/api/rcm/sub-processes",
        lookup_key="code",
        lookup_value="P-SALES-010",
        payload={"code": "P-SALES-010", "name": "주문 및 거래관리", "process_id": process["id"]},
    )
    ctx.ids["sub_process_P-SALES-010"] = sp["id"]

    # Risk
    risk = get_or_create(
        ctx,
        list_path="/api/rcm/risks",
        create_path="/api/rcm/risks",
        lookup_key="code",
        lookup_value="P-SALES-010-10",
        payload={
            "code": "P-SALES-010-10",
            "description": "매출 인식 위험 — 계약 조건 미충족 매출 조기 인식",
            "assessment_level": "LR",
            "sub_process_id": sp["id"],
        },
    )
    ctx.ids["risk_P-SALES-010-10"] = risk["id"]

    # Controls (2개)
    ctl1 = get_or_create(
        ctx,
        list_path="/api/rcm/controls",
        create_path="/api/rcm/controls",
        lookup_key="code",
        lookup_value="P-SALES-010-10-10",
        payload={
            "code": "P-SALES-010-10-10",
            "name": "매출 인식 검토 통제",
            "objective": "계약 조건 충족 여부 검토 후 매출 인식",
            "owner_name": "재무팀장",
            "risk_id": risk["id"],
            "is_key_control": True,
            "preventive_detective": "P",
            "auto_manual": "M",
            "activity_approval": True,
            "frequency": "M",
            "ipe_relevant": "N/A",
        },
    )
    ctx.ids[MAIN_CONTROL_KEY] = ctl1["id"]

    ctl2 = get_or_create(
        ctx,
        list_path="/api/rcm/controls",
        create_path="/api/rcm/controls",
        lookup_key="code",
        lookup_value="P-SALES-010-10-20",
        payload={
            "code": "P-SALES-010-10-20",
            "name": "매출 마감 통제",
            "risk_id": risk["id"],
            "frequency": "M",
            "preventive_detective": "D",
            "auto_manual": "M",
        },
    )
    ctx.ids["control_P-SALES-010-10-20"] = ctl2["id"]

    # RiskCategories (assertion 표준 7종)
    for code, name in [
        ("E", "Existence"), ("C", "Completeness"), ("R", "Rights & Obligations"),
        ("V", "Valuation"), ("P", "Presentation"), ("O", "Occurrence"), ("M", "Measurement"),
    ]:
        rc = get_or_create(
            ctx,
            list_path="/api/rcm/risk-categories",
            create_path="/api/rcm/risk-categories",
            lookup_key="code",
            lookup_value=code,
            payload={"code": code, "name": name},
        )
        ctx.ids[f"rc_{code}"] = rc["id"]

    # ControlAssertions: C1 ↔ E·C, C2 ↔ V
    existing_ca = ctx.get("/api/rcm/control-assertions")
    existing_pairs = {
        (ca["control_id"], ca["risk_category_id"])
        for ca in existing_ca.get("items", [])
    }
    for ctl_key, rc_key in [
        (MAIN_CONTROL_KEY, "rc_E"),
        (MAIN_CONTROL_KEY, "rc_C"),
        ("control_P-SALES-010-10-20", "rc_V"),
    ]:
        ctl_id = ctx.ids[ctl_key]
        rc_id = ctx.ids[rc_key]
        if (ctl_id, rc_id) in existing_pairs:
            print(f"  [control-assertions] {ctl_key}↔{rc_key} exists (skip)")
            continue
        ctx.post("/api/rcm/control-assertions", {"control_id": ctl_id, "risk_category_id": rc_id})
        print(f"  [control-assertions] {ctl_key}↔{rc_key} created")
