"""재무제표 업로드 실 샘플 회귀 (8-B) — **로컬 전용**.

실 샘플(2025 감사 완료본)은 저장소에 넣지 않는다(마스터 확정 Q1). 환경변수로 경로를 줄 때만 돈다.
CI 에는 파일이 없으므로 skip 된다.

    FS_SAMPLE_FILE="<경로>/2025 재무제표 및 주석_…_감사수정사항반영.xlsx" pytest tests/test_fs_upload_real_sample.py

STEP 0 실측(prompts/ICFR_backend_fs-8b_20260929.md 0.3)을 고정한다.
"""
import json
import os
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import fs_upload
from app.services.fs_upload import structure
from tests import _fs_approval as fsa
from tests.test_fs_upload import XLSX, _tenant

D = Decimal
SAMPLE = os.environ.get("FS_SAMPLE_FILE")
pytestmark = pytest.mark.skipif(not SAMPLE or not Path(SAMPLE).is_file(),
                                reason="FS_SAMPLE_FILE 미지정 — 실 샘플 회귀는 로컬 전용")


@pytest.fixture(scope="module")
def content() -> bytes:
    return Path(SAMPLE).read_bytes()


@pytest.fixture(scope="module")
def wb(content):
    return fs_upload.open_workbook(content)


def test_candidates(wb) -> None:
    got = {(c["sheet"], c["kind"], c["statement_type"]) for c in fs_upload.scan(wb)}
    assert got == {("BS공시", "disclosure_form", "BS"), ("PL공시", "disclosure_form", "PL"),
                   ("CF공시", "disclosure_form", "CF"), ("BS정산표", "horizontal_years", "BS"),
                   ("PL정산표", "horizontal_years", "PL")}


@pytest.mark.parametrize("sheet", ["BS공시", "PL공시", "CF공시"])
def test_disclosure_sheets_have_no_subtotal_diffs(wb, sheet) -> None:
    s = fs_upload.parse_sheet(wb[sheet])
    assert s.errors == [] and s.periods == [2025, 2024] and s.unit == 1
    assert structure.subtotal_diffs(s) == []


def test_horizontal_findings(wb) -> None:
    bs = fs_upload.parse_sheet(wb["BS정산표"])
    assert bs.periods == [2025, 2024, 2023, 2022, 2021, 2020]
    # 원본 수식 누락 — 지배주주지분 = 자본금 + 자본잉여금 + 이익잉여금(자본조정·기타포괄 빠짐)
    assert {d["label"] for d in structure.subtotal_diffs(bs)} == {"지배주주의소유주에게귀속되는지분", "자본총계"}
    pl = fs_upload.parse_sheet(wb["PL정산표"])
    assert pl.periods == [2025, 2024, 2023] and any("2022" in w for w in pl.warnings)
    assert structure.subtotal_diffs(pl) == []
    assert fs_upload.parse_sheet(wb["CE공시"]).statement_type == "SCE"


@pytest.mark.parametrize("sheet", ["BS공시", "PL공시", "CF공시"])
def test_disclosure_commit_passes_gate(client: TestClient, content, sheet) -> None:
    """실 데이터로 8-A 확정 관문(자산=부채+자본·소계)을 통과해 final 이 된다."""
    h, _ = _tenant(client)
    r = client.post("/api/fs/upload", headers=h, data={"mode": "commit", "sheet": sheet, "include_prior": "true"},
                    files={"file": ("sample.xlsx", content, XLSX)})
    assert r.status_code == 200, r.text
    sts = {s["fiscal_year"]: s for s in r.json()["statements"]}
    assert sts[2025]["status"] == "draft" and sts[2025]["review_requested"] and sts[2025]["ok"]
    assert sts[2024]["ok"] and sts[2024]["status"] == "draft"


def test_horizontal_pl_commit(client: TestClient, content) -> None:
    h, _ = _tenant(client)
    r = client.post("/api/fs/upload", headers=h, data={"mode": "commit", "sheet": "PL정산표", "unit": "1"},
                    files={"file": ("sample.xlsx", content, XLSX)})
    assert r.status_code == 200, r.text
    assert {s["fiscal_year"]: s["review_requested"] for s in r.json()["statements"]} == \
        {2025: True, 2024: False, 2023: False}


# ── 8-B2 정산표 결합 (8-C STEP 0 0.3 실측 고정) ──────────────────

PL_CATEGORY_MAP = {"매출액": "영업수익", "판매비와관리비": "영업비용", "금융이익": "금융수익", "금융원가": "금융비용",
                   "기타영업외이익": "기타영업외수익", "기타영업외비용": "기타영업외비용", "법인세비용": "법인세비용"}


def _up(client, h, content, path="/api/fs/upload", **data):
    return client.post(path, headers=h, data={k: str(v) for k, v in data.items()},
                       files={"file": ("sample.xlsx", content, XLSX)})


def _reopen_2025(client, h, sts) -> None:
    sid = next(s["statement_id"] for s in sts if s["fiscal_year"] == 2025)
    assert fsa.withdraw(client, sid, h).status_code == 200


@pytest.mark.parametrize("stype,disc,hz,extra", [
    ("BS", "BS공시", "BS정산표", {}),
    ("PL", "PL공시", "PL정산표", {"category_map": json.dumps(PL_CATEGORY_MAP)}),   # 분류명 → 공시 행(추정 금지)
])
def test_attach_worksheet_to_disclosure(client: TestClient, content, stype, disc, hz, extra) -> None:
    """공시 행 = COA 합이 두 연도 모두 맞아 결합 후에도 8-A 관문을 통과한다(BS 58/58·PL 14/14)."""
    h, _ = _tenant(client)
    up = _up(client, h, content, mode="commit", sheet=disc, include_prior="true")
    assert up.status_code == 200, up.text
    sts = up.json()["statements"]

    blocked = _up(client, h, content, "/api/fs/upload/attach", mode="commit", sheet=hz, unit=1, **extra)
    assert blocked.status_code == 409                                   # 2025 는 final — 재오픈 후
    pre = _up(client, h, content, "/api/fs/upload/attach", mode="preview", sheet=hz, unit=1, **extra).json()
    assert pre["errors"] == [], pre["errors"]
    assert pre["fiscal_years"] == [2025, 2024] and all(s["ok"] for s in pre["statements"]), pre["statements"]

    _reopen_2025(client, h, sts)
    com = _up(client, h, content, "/api/fs/upload/attach", mode="commit", sheet=hz, unit=1, **extra)
    assert com.status_code == 200, com.text
    got = {s["fiscal_year"]: (s["ok"], s["status"]) for s in com.json()["statements"]}
    assert got == {2025: (True, "draft"), 2024: (True, "draft")}
    names = {r["name"] for r in com.json()["rows"]}
    if stype == "BS":
        assert {"감가상각누계액_건물", "감가상각누계액_차량운반구", "감가상각누계액_비품"} <= names


# ── 8-C 템플릿 제안 (실 데이터 마스터) ─────────────────────────

@pytest.fixture(scope="module")
def real_master(client: TestClient, content):
    """공시 BS·PL·CF(2025·2024) + 정산표 BS·PL 결합 — 8-B2 까지 마친 실 데이터 마스터."""
    from seeds.seed_scoping_template import load_template
    from tests.conftest import TestingSessionLocal
    db = TestingSessionLocal()
    try:
        _, _, created = load_template(db)
        if created:
            db.commit()
    finally:
        db.close()
    h, _ = _tenant(client)
    for disc, hz, extra in (("BS공시", "BS정산표", {}), ("PL공시", "PL정산표", {"category_map": json.dumps(PL_CATEGORY_MAP)}),
                            ("CF공시", None, {})):
        up = _up(client, h, content, mode="commit", sheet=disc, include_prior="true", finalize="false")
        assert up.status_code == 200, up.text
        if hz:
            r = _up(client, h, content, "/api/fs/upload/attach", mode="commit", sheet=hz, unit=1, **extra)
            assert r.status_code == 200, r.text
    return h


def _suggest_summary(client, h, stype) -> dict:
    m = client.get("/api/fs/template-matches", headers=h, params={"statement_type": stype}).json()
    used = {r["suggestion"]["template_account_id"] for r in m["accounts"] if r["suggestion"]}
    return {"accounts": len(m["accounts"]), "templates": len(m["template_accounts"]),
            "exact": sum(1 for r in m["accounts"] if (r["suggestion"] or {}).get("basis") == "exact"),
            "normalized": sum(1 for r in m["accounts"] if (r["suggestion"] or {}).get("basis") == "normalized"),
            "templates_covered": len(used),
            "templates_left": sorted(t["name"] for t in m["template_accounts"] if t["id"] not in used)}


@pytest.mark.parametrize("stype", ["BS", "PL", "CF"])
def test_template_suggestions_on_real_master(client: TestClient, real_master, stype) -> None:
    """2026-09-30 실측 고정 — 남는 것은 회사 쪽 반복 이름(감가상각누계액·리스부채·정부보조금)이나 회사에
    없는 계정(선수수익·대여금 등)으로 수동 대상이다."""
    s = _suggest_summary(client, real_master, stype)
    assert s["templates_covered"] == {"BS": 48, "PL": 45, "CF": 35}[stype], s


# ── 임시계정(원본 차이) — 실측 지배주주지분 수식 누락 ────────────────

def test_real_equity_difference_goes_to_suspense_and_fix_resolves(client: TestClient, content) -> None:
    """BS정산표 지배주주지분(자본조정·기타포괄 누락) 차이가 연도마다 임시계정으로 가고, 소계 정정으로 풀린다."""
    h, _ = _tenant(client)
    r = _up(client, h, content, mode="commit", sheet="BS정산표", unit=1)
    assert r.status_code == 200, r.text
    expected = {2025: D(244742730), 2024: D(235170378), 2023: D(226013853), 2022: D(253852819),
                2021: D(253316099), 2020: D(241331027)}
    for s in r.json()["statements"]:
        got = {x["parent_name"]: D(x["amount"]) for x in s["suspense"]}
        assert got == {"지배주주의소유주에게귀속되는지분": expected[s["fiscal_year"]],
                       "자본총계": -expected[s["fiscal_year"]]}, (s["fiscal_year"], got)
        assert s["status"] == "draft"
    sid = next(s["statement_id"] for s in r.json()["statements"] if s["fiscal_year"] == 2025)
    items = client.get(f"/api/fs/statements/{sid}/suspense", headers=h).json()
    aid = next(x["amount_id"] for x in items if x["parent_name"] == "지배주주의소유주에게귀속되는지분")
    fixed = client.post(f"/api/fs/statements/{sid}/suspense/{aid}/resolve", headers=h,
                        json={"action": "fix_subtotal", "reason": "정산표 수식 누락(자본조정·기타포괄)"})
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["validation"]["ok"], fixed.json()["validation"]["errors"]


# ── 8-E 재무제표 기반 스코핑 (실 데이터) ──────────────────────────

def test_real_scoping_from_financial_statements(client: TestClient, content) -> None:
    """공시 BS·PL·CF + 정산표 결합 + 정확일치 링크 확정 → 2026 스코핑을 재무제표에서 만든다."""
    from seeds.seed_scoping_template import load_template
    from tests.conftest import TestingSessionLocal
    db = TestingSessionLocal()
    try:
        _, _, created = load_template(db)
        if created:
            db.commit()
    finally:
        db.close()
    h, _ = _tenant(client)
    for disc, hz, extra in (("BS공시", "BS정산표", {}), ("PL공시", "PL정산표", {"category_map": json.dumps(PL_CATEGORY_MAP)}),
                            ("CF공시", None, {})):
        up = _up(client, h, content, mode="commit", sheet=disc, include_prior="true", finalize="false")
        assert up.status_code == 200, up.text
        if hz:
            r = _up(client, h, content, "/api/fs/upload/attach", mode="commit", sheet=hz, unit=1, finalize="false", **extra)
            assert r.status_code == 200, r.text
        for s in up.json()["statements"]:
            f = fsa.confirm(client, s["statement_id"], h)
            assert f.status_code == 200, (disc, s["fiscal_year"], f.text[:300])
    for stype in ("BS", "PL", "CF"):
        m = client.get("/api/fs/template-matches", headers=h, params={"statement_type": stype}).json()
        links = [{"account_id": r["account_id"], "template_account_id": r["suggestion"]["template_account_id"]}
                 for r in m["accounts"] if r["suggestion"] and r["suggestion"]["basis"] == "exact" and not r["link"]]
        assert client.post("/api/fs/template-links", headers=h, json={"links": links}).status_code == 200
    r = client.post("/api/scoping", headers=h, json={"fiscal_year": 2026, "source": "financial_statements"})
    assert r.status_code == 201, r.text
    d = r.json()
    by = {t: [a for a in d["accounts"] if a["statement_type"] == t] for t in ("BS", "PL", "CF", "NOTE")}
    filled = {t: sum(1 for a in rows if a["ratings"]) for t, rows in by.items()}
    # 2026-09-30 실측 고정 — 행 수(금액 트리 잎)와 템플릿 기본값이 채워진 행 수. 정확일치로 연결돼도
    # 템플릿 계정 자체에 질적 평가값이 없는 경우가 있어 채워진 수가 연결 수보다 적다
    assert {t: (len(rows), filled[t]) for t, rows in by.items()} ==         {"BS": (71, 35), "PL": (56, 41), "CF": (47, 31), "NOTE": (38, 38)}
    assert all(a["fs_account_id"] for t in ("BS", "PL", "CF") for a in by[t])
    cash = next(a for a in by["BS"] if a["name"] == "현금및현금성자산" and a["group_label"] == "현금및현금성자산")
    assert cash["current_amount"] == 44249836141 and cash["prior_amount"] == 43868110698
