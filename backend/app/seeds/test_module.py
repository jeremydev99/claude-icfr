from app.seeds._shared import SeedContext
from app.seeds.rcm import MAIN_CONTROL_KEY

FISCAL_YEAR = 2026


def seed(ctx: SeedContext) -> None:
    """RAWC 평가 + TestRun (Phase 1 작업3 구조)."""

    control_id = ctx.ids.get(MAIN_CONTROL_KEY)
    tester_id = ctx.ids.get("tester@acme.example")

    if not control_id:
        print("  [test_module] MAIN_CONTROL 없음 — RCM 시드 먼저 필요")
        return

    # RAWC 평가 (control_id + fiscal_year 복합 유일)
    rawc_list = ctx.get("/api/test/rawc", params={"control_id": control_id, "fiscal_year": FISCAL_YEAR})
    if rawc_list.get("total", 0) > 0:
        print(f"  [rawc] control_id={control_id} fy={FISCAL_YEAR} exists (skip)")
        rawc = rawc_list["items"][0]
    else:
        rawc = ctx.post("/api/test/rawc", {
            "control_id": control_id,
            "fiscal_year": FISCAL_YEAR,
            "frequency_score": 2,
            "nature_score": 2,
            "precision_score": 2,
            "dependency_score": 2,
            "automation_score": 2,
            "authority_score": 2,
            "review_score": 2,
            "prior_year_effectiveness": "Effective",
            "overall_assessment": "Not_Higher",
        })
        print(f"  [rawc] created (id={rawc['id']})")
    ctx.ids["rawc_001"] = rawc["id"]

    # TestRun (control_id + fiscal_year 복합 유일)
    runs = ctx.get("/api/test/runs", params={"fiscal_year": FISCAL_YEAR})
    run_obj = next((r for r in runs.get("items", []) if r["control_id"] == control_id), None)

    if run_obj:
        print(f"  [test_runs] fy={FISCAL_YEAR} control exists (skip)")
    else:
        run_obj = ctx.post("/api/test/runs", {
            "control_id": control_id,
            "fiscal_year": FISCAL_YEAR,
            "tester_id": tester_id,
            "method_inquiry": True,
            "method_inspection": True,
            "population": f"{FISCAL_YEAR}년 전체 매출 거래",
            "test_frequency": "M",
            "sample_size": 25,
            "procedure": "샘플 25건 매출 인식 검토 — 계약 조건 충족 여부 확인",
        })
        print(f"  [test_runs] created (id={run_obj['id']})")
    ctx.ids["test_run_001"] = run_obj["id"]

    # TestSteps
    existing_steps = ctx.get("/api/test/steps", params={"run_id": run_obj["id"]})
    if existing_steps.get("total", 0) >= 2:
        print(f"  [test_steps] run steps exist (skip)")
    else:
        for order, desc, result in [
            (1, "계약서 및 배송 확인서 샘플 추출", "pass"),
            (2, "회계 처리일과 수익 인식 기준일 일치 여부 검토", "pass"),
        ]:
            ctx.post("/api/test/steps", {
                "test_run_id": run_obj["id"],
                "step_order": order,
                "description": desc,
                "result": result,
            })
            print(f"  [test_steps] step {order} created")

    # 워크플로 전이: planned → in_progress
    if run_obj.get("status") == "planned":
        ctx.post(f"/api/test/runs/{run_obj['id']}/transition", {
            "to_status": "in_progress",
            "reason": "시드 데이터 — Tester 평가 시작",
        })
        print(f"  [test_runs] transitioned → in_progress")
    else:
        print(f"  [test_runs] status={run_obj.get('status')} (skip transition)")
