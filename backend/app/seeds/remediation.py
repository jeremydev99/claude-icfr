from app.seeds._shared import SeedContext, get_or_create


def seed(ctx: SeedContext) -> None:
    """Deficiency + RemediationPlan 시드 데이터."""

    reviewer_id = ctx.ids.get("reviewer@acme.example")

    # Deficiency
    deficiency = get_or_create(
        ctx,
        list_path="/api/remediation/deficiencies",
        create_path="/api/remediation/deficiencies",
        lookup_key="code",
        lookup_value="D-001",
        payload={
            "code": "D-001",
            "severity": "medium",
            "description": "매출 마감 통제(C-002) 수행 증빙 누락 — 2건의 샘플에서 승인 서명 미비 확인",
            "status": "open",
        },
    )
    ctx.ids["deficiency_D001"] = deficiency["id"]

    if not reviewer_id:
        print("  [remediation] reviewer_id 누락 — RemediationPlan 건너뜀")
        return

    # RemediationPlan
    existing_plans = ctx.get("/api/remediation/plans")
    existing = next(
        (p for p in existing_plans.get("items", []) if p["deficiency_id"] == deficiency["id"]),
        None,
    )
    if existing:
        print(f"  [remediation_plans] deficiency_id={deficiency['id']} exists (skip)")
    else:
        ctx.post("/api/remediation/plans", {
            "deficiency_id": deficiency["id"],
            "owner_id": reviewer_id,
            "target_date": "2026-06-30",
            "action_plan": "통제 수행 절차서 재교육 후 승인 서명 프로세스 강화. 매월 말 통제 수행 직후 당일 서명 완료 의무화.",
        })
        print(f"  [remediation_plans] deficiency D-001 plan created")
