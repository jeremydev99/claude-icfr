from app.seeds._shared import SeedContext
from app.seeds.rcm import MAIN_CONTROL_KEY

FISCAL_YEAR = 2026


def seed(ctx: SeedContext) -> None:
    """RAWC 평가. TestRun 은 폐지(2026-10-15) — 테스트는 평가 회차 활동으로 기록한다."""

    control_id = ctx.ids.get(MAIN_CONTROL_KEY)

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
