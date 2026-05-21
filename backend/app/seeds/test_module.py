from app.seeds._shared import SeedContext


def seed(ctx: SeedContext) -> None:
    """TestRun + TestStep 시드 데이터."""

    control_id = ctx.ids.get("control_C-001")
    tester_id = ctx.ids.get("tester@acme.example")

    if not control_id or not tester_id:
        print("  [test_module] 필수 ID 누락 (control_C-001 또는 tester). RCM/Users 시드 먼저 실행 필요.")
        return

    # TestRun
    existing = ctx.get("/api/test/runs")
    run_obj = next((r for r in existing.get("items", []) if r["control_id"] == control_id), None)

    if run_obj:
        print(f"  [test_runs] control_id={control_id} exists (skip)")
    else:
        run_obj = ctx.post("/api/test/runs", {
            "control_id": control_id,
            "tester_id": tester_id,
            "test_date": "2026-03-31",
            "result": "pass",
            "notes": "매출 인식 검토 통제 1분기 운영평가 — Pass",
        })
        print(f"  [test_runs] created (id={run_obj['id']})")
    ctx.ids["test_run_001"] = run_obj["id"]

    # TestSteps
    existing_steps = ctx.get("/api/test/steps", params={"run_id": run_obj["id"]})
    if existing_steps.get("total", 0) >= 2:
        print(f"  [test_steps] run_id={run_obj['id']} steps exist (skip)")
        return

    for order, desc, result in [
        (1, "매출 전표 샘플 30건 추출 및 승인 서명 확인", "pass"),
        (2, "매출 인식 기준일과 회계 처리일 일치 여부 검토", "pass"),
    ]:
        ctx.post("/api/test/steps", {
            "test_run_id": run_obj["id"],
            "step_order": order,
            "description": desc,
            "result": result,
        })
        print(f"  [test_steps] step {order} created")
