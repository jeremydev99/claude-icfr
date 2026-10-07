"""회계연도 RCM 확정 결재 (ADR-0038 2-5) — 결재선·스냅샷·라이브 RCM 잠금·재오픈·다음 연도."""
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.tenant_context import reset_active_tenant, set_active_tenant
from app.models.control_change import CH_DEPT_REVIEW, ControlChange
from app.models.rcm_baseline import (
    BaselineControl,
    BaselineProcess,
    BaselineRisk,
    BaselineSubProcess,
)
from app.services import approval_flow
from tests.conftest import TestingSessionLocal
from tests.test_governance import T

Y = "/api/rcm-years"


@pytest.fixture(autouse=True)
def no_minio(monkeypatch):
    monkeypatch.setattr(approval_flow, "upload_object", lambda key, data, mime: None)


def _control(t: T) -> str:
    db = TestingSessionLocal()
    tok = set_active_tenant(t.tid)
    try:
        tag = uuid4().hex[:5]
        p = BaselineProcess(code=f"RY{tag}-P", name="P")
        db.add(p)
        db.flush()
        sp = BaselineSubProcess(code=f"RY{tag}-SP", name="SP", process_id=p.id)
        db.add(sp)
        db.flush()
        r = BaselineRisk(code=f"RY{tag}-R", description="R", assessment_level="LR", sub_process_id=sp.id)
        db.add(r)
        db.flush()
        c = BaselineControl(code=f"RY{tag}-C", name="통제", risk_id=r.id, assessment_frequency="annual")
        db.add(c)
        db.commit()
        return str(c.id)
    finally:
        reset_active_tenant(tok)
        db.close()


def _start(client, t, who="lead", year=2026) -> str:
    r = client.post(Y, headers=t.h[who], json={"fiscal_year": year})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _to(client, t, who, rid, to, reason=None):
    return client.post(f"{Y}/{rid}/transition", headers=t.h[who], json={"to_status": to, "reason": reason})


def _confirm(client, t, rid):
    assert _to(client, t, "lead", rid, "review").status_code == 200
    r = _to(client, t, "master", rid, "confirmed", "2026 RCM 확정")
    assert r.status_code == 200, r.text
    return r.json()


def test_every_rcm_write_route_is_locked() -> None:
    """RCM 쓰기 경로는 전부 잠금 의존성을 단다 — 새 경로가 빠지면 여기서 잡힌다(엑셀 업로드는 저장 시 함수 안에서)."""
    from app.api.rcm import require_rcm_editable
    from app.main import app
    missing = []
    for r in app.routes:
        path = getattr(r, "path", "")
        if not path.startswith("/api/rcm/") or path.endswith("/upload-excel"):
            continue
        for m in (getattr(r, "methods", None) or ()):
            if m in ("POST", "PUT", "PATCH", "DELETE"):
                deps = [d.call for d in r.dependant.dependencies]
                if require_rcm_editable not in deps:
                    missing.append(f"{m} {path}")
    assert missing == []


def test_confirm_snapshot_and_lock(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})
    cid = _control(t)
    rid = _start(client, t)
    assert client.get(f"{Y}/lock", headers=t.h["lead"]).json()["locked"] is False      # 작성 중은 열려 있다
    assert _to(client, t, "lead", rid, "confirmed", "x").status_code == 409            # 검토 요청 전
    assert _to(client, t, "lead", rid, "review").status_code == 200
    lock = client.get(f"{Y}/lock", headers=t.h["lead"]).json()
    assert lock["locked"] and "검토 중" in lock["reason"]
    assert _to(client, t, "lead", rid, "confirmed", "x").status_code == 403            # 요청자·책임관리자
    d = _to(client, t, "master", rid, "confirmed", "2026 RCM 확정").json()
    assert d["approval_status"] == "confirmed" and d["snapshots"][0]["version"] == 1
    assert d["snapshots"][0]["control_count"] == 1
    snap = client.get(f"{Y}/{rid}/snapshots/1", headers=t.h["lead"]).json()
    assert [c["id"] for c in snap["controls"]] == [cid] and snap["fiscal_year"] == 2026
    # 잠금 — 마스터의 바로 반영도, 상위 계층 등록도, 엑셀 저장도 409
    assert client.patch(f"/api/rcm/controls/{cid}", headers=t.h["master"], json={"name": "새 이름"}).status_code == 409
    assert client.post("/api/rcm/processes", headers=t.h["master"], json={"code": "X", "name": "X"}).status_code == 409
    up = client.post("/api/rcm/upload-excel", headers=t.h["master"], data={"mode": "commit"},
                     files={"file": ("a.xlsx", b"x", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert up.status_code == 409


def test_reopen_bumps_version_and_keeps_old_snapshot(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})
    cid = _control(t)
    rid = _start(client, t)
    _confirm(client, t, rid)
    r = client.post(f"{Y}/{rid}/reopen-requests", headers=t.h["lead"], json={"reason": "설계변경 반영"})
    assert r.status_code == 201, r.text
    req = r.json()["governance"]["pending_reopen"]["id"]
    assert client.get(f"{Y}/lock", headers=t.h["lead"]).json()["locked"]               # 요청만으로는 잠긴 채
    r = client.post(f"{Y}/{rid}/reopen-requests/{req}/decide", headers=t.h["master"], json={"approve": True})
    assert r.status_code == 200 and r.json()["version"] == 2 and r.json()["approval_status"] == "draft"
    pr = client.patch(f"/api/rcm/controls/{cid}", headers=t.h["master"], json={"name": "개정 통제"})
    assert pr.status_code == 200, pr.text
    d = _confirm(client, t, rid)
    assert [s["version"] for s in d["snapshots"]] == [2, 1]
    assert client.get(f"{Y}/{rid}/snapshots/1", headers=t.h["lead"]).json()["controls"][0]["name"] == "통제"
    assert client.get(f"{Y}/{rid}/snapshots/2", headers=t.h["lead"]).json()["controls"][0]["name"] == "개정 통제"


def test_pending_control_changes_block_submit(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})
    cid = _control(t)
    rid = _start(client, t)
    db = TestingSessionLocal()
    tok = set_active_tenant(t.tid)
    try:
        db.add(ControlChange(control_id=UUID(cid), status=CH_DEPT_REVIEW, changes={"name": "x"},
                             author_id=UUID(t.uid["lead"])))
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()
    r = _to(client, t, "lead", rid, "review")
    assert r.status_code == 409 and "통제 변경 결재 1건" in r.json()["detail"]


def test_next_year_unlocks_and_old_year_is_fixed(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})
    _control(t)
    r2026 = _start(client, t)
    assert client.post(Y, headers=t.h["lead"], json={"fiscal_year": 2025}).status_code == 409   # 과거 연도
    _confirm(client, t, r2026)
    r2027 = _start(client, t, year=2027)
    assert client.get(f"{Y}/lock", headers=t.h["lead"]).json()["locked"] is False
    assert client.post(f"{Y}/{r2026}/reopen-requests", headers=t.h["lead"], json={"reason": "x"}).status_code == 409
    assert client.get(f"{Y}/{r2027}", headers=t.h["lead"]).json()["is_latest"]


def test_inbox_and_permissions(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",), "admin": ("sys_admin",)})
    _control(t)
    assert client.post(Y, headers=t.h["admin"], json={"fiscal_year": 2026}).status_code == 403
    rid = _start(client, t)
    assert _to(client, t, "lead", rid, "review").status_code == 200
    items = [i for i in client.get("/api/governance/inbox", headers=t.h["master"]).json()
             if i["entity_type"] == "rcm_fiscal_year"]
    assert [(i["entity_id"], i["action"]) for i in items] == [(rid, "approve")]


def test_lock_is_per_company(client: TestClient) -> None:
    """회사 A 의 확정이 회사 B 의 RCM 을 잠그면 안 된다 — 잠금 조회가 회사 필터보다 먼저 돌던 버그(2026-10-07)."""
    a = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})
    _control(a)
    _confirm(client, a, _start(client, a))
    b = T(client, {"master": ("icfr_manager",)})
    cid = _control(b)
    assert client.get(f"{Y}/lock", headers=b.h["master"]).json()["locked"] is False
    r = client.patch(f"/api/rcm/controls/{cid}", headers=b.h["master"], json={"name": "B 회사 수정"})
    assert r.status_code == 200, r.text
