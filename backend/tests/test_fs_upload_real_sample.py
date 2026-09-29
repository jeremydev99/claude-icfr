"""재무제표 업로드 실 샘플 회귀 (8-B) — **로컬 전용**.

실 샘플(2025 감사 완료본)은 저장소에 넣지 않는다(마스터 확정 Q1). 환경변수로 경로를 줄 때만 돈다.
CI 에는 파일이 없으므로 skip 된다.

    FS_SAMPLE_FILE="<경로>/2025 재무제표 및 주석_…_감사수정사항반영.xlsx" pytest tests/test_fs_upload_real_sample.py

STEP 0 실측(prompts/ICFR_backend_fs-8b_20260929.md 0.3)을 고정한다.
"""
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import fs_upload
from app.services.fs_upload import structure
from tests.test_fs_upload import XLSX, _tenant

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
    assert sts[2025]["status"] == "final" and sts[2025]["ok"]
    assert sts[2024]["ok"] and sts[2024]["status"] == "draft"


def test_horizontal_pl_commit(client: TestClient, content) -> None:
    h, _ = _tenant(client)
    r = client.post("/api/fs/upload", headers=h, data={"mode": "commit", "sheet": "PL정산표", "unit": "1"},
                    files={"file": ("sample.xlsx", content, XLSX)})
    assert r.status_code == 200, r.text
    assert {s["fiscal_year"]: s["status"] for s in r.json()["statements"]} == \
        {2025: "final", 2024: "draft", 2023: "draft"}
