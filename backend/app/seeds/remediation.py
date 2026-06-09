from app.seeds._shared import SeedContext, get_or_create


def seed(ctx: SeedContext) -> None:
    """Deficiency + RemediationPlan + DesignAssessment 시드 데이터."""

    reviewer_id = ctx.ids.get("reviewer@acme.example")
    tester_id = ctx.ids.get("tester@acme.example")
    owner_id = reviewer_id or tester_id

    # ── 통제 조회 (EL-010-10-10 사용, 없으면 skip) ─────────────
    controls = ctx.get("/api/rcm/controls")
    target_control = next(
        (c for c in controls.get("items", []) if c.get("code") == "EL-010-10-10"),
        None,
    )

    # ── DesignAssessment 1건 ────────────────────────────────────
    if target_control:
        existing_da = ctx.get(
            f"/api/remediation/design-assessments/by-control/{target_control['id']}",
            params={"fiscal_year": 2025},
        )
        if existing_da.get("total", 0) == 0:
            ctx.post("/api/remediation/design-assessments", {
                "control_id": target_control["id"],
                "fiscal_year": 2025,
                "design_score_1": 2,
                "design_score_2": 3,
                "design_score_3": 2,
                "design_score_4": 2,
                "design_score_5": 3,
                "design_score_6": 2,
                "design_score_7": 2,
                "design_score_8": 3,
                "overall_design": "Effective",
                "assessment_method": "Walkthrough",
                "performer_name": "내부 감사팀",
            })
            print(f"  [design_assessments] EL-010-10-10 / 2025 created")
        else:
            print(f"  [design_assessments] EL-010-10-10 / 2025 exists (skip)")
    else:
        print(f"  [design_assessments] EL-010-10-10 not found — skip")

    # ── Deficiency ──────────────────────────────────────────────
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
            "fiscal_year": 2025,
            "control_id": target_control["id"] if target_control else None,
        },
    )
    ctx.ids["deficiency_D001"] = deficiency["id"]

    if not owner_id:
        print("  [remediation] owner_id 누락 — RemediationPlan 건너뜀")
        return

    # ── RemediationPlan ──────────────────────────────────────────
    existing_plans = ctx.get("/api/remediation/plans")
    existing = next(
        (p for p in existing_plans.get("items", []) if p["deficiency_id"] == deficiency["id"]),
        None,
    )
    if existing:
        print(f"  [remediation_plans] deficiency_id={deficiency['id']} exists (skip)")
    else:
        plan = ctx.post("/api/remediation/plans", {
            "deficiency_id": deficiency["id"],
            "owner_id": owner_id,
            "target_date": "2026-12-31",
            "action_plan": "통제 수행 절차서 재교육 후 승인 서명 프로세스 강화. 매월 말 통제 수행 직후 당일 서명 완료 의무화.",
            "improvement_description": "승인 서명 프로세스 개선 및 담당자 교육 실시",
            "priority": "Medium",
        })
        print(f"  [remediation_plans] deficiency D-001 plan created, status={plan.get('status')}")

        # 전이: planned → in_progress
        ctx.post(
            f"/api/remediation/plans/{plan['id']}/transition",
            {"to_status": "in_progress", "reason": "시드 — 개선 시작"},
        )
        print(f"  [remediation_plans] transitioned to in_progress")
