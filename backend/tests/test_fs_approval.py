"""재무제표 결재 (ADR-0038 2-1·2-2) — 확정은 결재선으로만, 자기 승인 금지, 검토 중 잠금, 재오픈 승인, 이전 방식 확정.

테스트마다 **새 테넌트**(`test_governance.T`) — 승인 경로가 "책임관리자가 있는가"에 달려 있다.
"""
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.tenant_context import reset_active_tenant, set_active_tenant
from app.models.governance import ApprovalState
from app.services import approval_flow
from app.services import financial_statement as svc
from tests.conftest import TestingSessionLocal
from tests.test_governance import T

BAL = {"A": 100, "CA": 100, "cash": 100, "L": 60, "ap": 60, "E": 40, "cs": 40}



@pytest.fixture(autouse=True)
def no_minio(monkeypatch):
    stored = {}
    monkeypatch.setattr(approval_flow, "upload_object", lambda key, data, mime: stored.__setitem__(key, data))
    return stored


def _statement(t: T, year: int = 2025, amounts: dict | None = None, *, final_by: str | None = None) -> str:
    """균형 잡힌 재무상태표 1건(테넌트 `t`). `final_by` 를 주면 **2단계 이전 방식**으로 바로 확정해 둔다."""
    amounts = amounts or BAL
    db = TestingSessionLocal()
    tok = set_active_tenant(t.tid)
    try:
        tag, c, acc = uuid4().hex[:6], svc.create_account, {}
        acc["A"] = c(db, statement_type="BS", name=f"자산총계{tag}", section="asset", is_subtotal=True)
        acc["CA"] = c(db, statement_type="BS", name=f"유동자산{tag}", section="asset", is_subtotal=True,
                      parent_id=acc["A"].id)
        acc["cash"] = c(db, statement_type="BS", name=f"현금{tag}", section="asset", parent_id=acc["CA"].id)
        acc["L"] = c(db, statement_type="BS", name=f"부채총계{tag}", section="liability", is_subtotal=True)
        acc["ap"] = c(db, statement_type="BS", name=f"매입채무{tag}", section="liability", parent_id=acc["L"].id)
        acc["E"] = c(db, statement_type="BS", name=f"자본총계{tag}", section="equity", is_subtotal=True)
        acc["cs"] = c(db, statement_type="BS", name=f"자본금{tag}", section="equity", parent_id=acc["E"].id)
        st = svc.create_statement(db, fiscal_year=year, statement_type="BS", basis="separate", unit=1)
        for k, a in acc.items():
            svc.set_amount(db, st, a, Decimal(amounts[k]))
        if final_by:
            svc.finalize(db, st, UUID(t.uid[final_by]), "이전 방식 확정")
        db.commit()
        return str(st.id)
    finally:
        reset_active_tenant(tok)
        db.close()


def _url(sid: str) -> str:
    return f"/api/fs/statements/{sid}"


def _to(client, t, who, sid, to, reason=None):
    return client.post(f"{_url(sid)}/transition", headers=t.h[who], json={"to_status": to, "reason": reason})


def _get(client, t, who, sid) -> dict:
    r = client.get(_url(sid), headers=t.h[who])
    assert r.status_code == 200, r.text
    return r.json()


def test_old_single_person_endpoints_removed(client: TestClient) -> None:
    t = T(client, {"master": ("icfr_manager",)})
    sid = _statement(t)
    assert client.post(f"{_url(sid)}/finalize", headers=t.h["master"], json={}).status_code in (404, 405)
    assert client.post(f"{_url(sid)}/reopen", headers=t.h["master"], json={"reason": "x"}).status_code in (404, 405)


def test_lead_submit_master_approve(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})
    sid = _statement(t)
    d = _get(client, t, "lead", sid)
    assert d["approval_status"] == "draft" and d["governance"]["preview_path"] == "master"
    assert _to(client, t, "lead", sid, "review").status_code == 200
    # 검토 중: 요청자 본인 승인 불가(책임관리자라 403), 마스터 승인 사유 필수
    assert _to(client, t, "lead", sid, "confirmed", "x").status_code == 403
    assert _to(client, t, "master", sid, "confirmed").status_code == 422
    r = _to(client, t, "master", sid, "confirmed", "결산 확정")
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["status"], d["approval_status"], d["legacy_confirmed"]) == ("final", "confirmed", False)
    assert d["governance"]["confirmed_by"]["name"] == "master"
    assert d["events"][-1]["actor_id"] == t.uid["master"]
    acts = [e["action"] for e in client.get(f"{_url(sid)}/governance-events", headers=t.h["lead"]).json()]
    assert acts == ["approve", "submit_review"]                                  # 최신순


def test_staff_path_requires_lead_review_before_master(client: TestClient) -> None:
    t = T(client, {"staff": ("icfr_staff",), "lead": ("icfr_lead",), "master": ("icfr_manager",)})
    sid = _statement(t)
    assert _to(client, t, "staff", sid, "review").status_code == 200
    assert _get(client, t, "staff", sid)["governance"]["review_path"] == "lead_then_master"
    assert _to(client, t, "master", sid, "confirmed", "먼저").status_code == 409   # 검토 전 승인 불가
    rv = client.post(f"{_url(sid)}/review", headers=t.h["lead"], json={"action": "done"})
    assert rv.status_code == 200, rv.text
    # 검토자 본인은 승인 불가(마스터가 아니라 403), 마스터는 승인
    assert _to(client, t, "lead", sid, "confirmed", "x").status_code == 403
    assert _to(client, t, "master", sid, "confirmed", "확정").status_code == 200


def test_master_submission_needs_external_approval_with_evidence(client: TestClient, no_minio) -> None:
    t = T(client, {"master": ("icfr_manager",), "master2": ("icfr_manager",)})
    sid = _statement(t)
    assert _to(client, t, "master", sid, "review").status_code == 200
    assert _get(client, t, "master", sid)["governance"]["review_path"] == "external"
    # 다른 마스터라도 내부 승인 불가 — 대표이사·이사회 승인 증빙으로만
    assert _to(client, t, "master2", sid, "confirmed", "x").status_code == 409
    form = {"purpose": "approve", "approver_body": "board", "approved_on": "2026-03-20", "reference": "제5차 이사회"}
    no_file = client.post(f"{_url(sid)}/external-approval", headers=t.h["master"], data=form,
                          files={"files": ("", b"", "application/pdf")})
    assert no_file.status_code == 422
    r = client.post(f"{_url(sid)}/external-approval", headers=t.h["master"], data=form,
                    files={"files": ("minutes.pdf", b"%PDF-1.4", "application/pdf")})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "final" and d["approval_status"] == "confirmed"
    assert d["governance"]["external_approvals"][0]["files"][0]["filename"] == "minutes.pdf"
    assert len(no_minio) == 1 and next(iter(no_minio)).split("/")[2] == "fs_statement"


def test_review_locks_statement_and_withdraw_unlocks(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})
    sid = _statement(t)
    assert _to(client, t, "lead", sid, "review").status_code == 200
    assert client.patch(_url(sid), headers=t.h["master"], json={"tolerance": "1"}).status_code == 409
    db = TestingSessionLocal()
    tok = set_active_tenant(t.tid)
    try:
        st = svc.get_statement(db, UUID(sid))
        acc = svc.statement_rows(db, st)[0][1]
        with pytest.raises(svc.FsConflictError, match="검토 중"):
            svc.set_amount(db, st, acc, 1)
        with pytest.raises(svc.FsConflictError, match="검토 중"):
            svc.set_subtotal(db, acc, not acc.is_subtotal)
    finally:
        db.rollback()
        reset_active_tenant(tok)
        db.close()
    # 회수는 요청자만, 반려는 승인권자가 사유와 함께
    assert _to(client, t, "master", sid, "draft").status_code == 422             # 반려 사유 없음
    assert _to(client, t, "lead", sid, "draft").status_code == 200               # 회수
    assert client.patch(_url(sid), headers=t.h["master"], json={"tolerance": "1"}).status_code == 200


def test_submit_blocked_by_validation(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",)})
    sid = _statement(t, amounts={**BAL, "cash": 90})
    r = _to(client, t, "lead", sid, "review")
    assert r.status_code == 422
    assert r.json()["detail"]["validation"]["errors"]
    assert _get(client, t, "lead", sid)["approval_status"] == "draft"


def test_reopen_needs_other_master_and_bumps_version(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})
    sid = _statement(t)
    assert _to(client, t, "lead", sid, "review").status_code == 200
    assert _to(client, t, "master", sid, "confirmed", "확정").status_code == 200
    assert _to(client, t, "master", sid, "draft").status_code == 409             # 직접 재오픈 불가
    r = client.post(f"{_url(sid)}/reopen-requests", headers=t.h["lead"], json={"reason": "명백한 오류"})
    assert r.status_code == 201, r.text
    rid = r.json()["governance"]["pending_reopen"]["id"]
    assert r.json()["status"] == "final"                                         # 요청만으로는 그대로
    assert client.post(f"{_url(sid)}/reopen-requests", headers=t.h["lead"], json={"reason": "또"}).status_code == 409
    dec = f"{_url(sid)}/reopen-requests/{rid}/decide"
    assert client.post(dec, headers=t.h["lead"], json={"approve": True}).status_code == 403
    assert client.post(dec, headers=t.h["master"], json={"approve": False}).status_code == 422   # 거절 사유
    r = client.post(dec, headers=t.h["master"], json={"approve": True})
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["status"], d["approval_status"], d["governance"]["version"]) == ("draft", "draft", 2)


def test_legacy_confirmed_statement(client: TestClient) -> None:
    """2단계 이전에 마스터 단독으로 확정된 재무제표 — 그대로 인정(Q3), 재오픈은 새 경로로."""
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",), "master2": ("icfr_manager",)})
    sid = _statement(t, final_by="master")
    d = _get(client, t, "lead", sid)
    assert (d["status"], d["approval_status"], d["legacy_confirmed"]) == ("final", "confirmed", True)
    assert d["governance"]["confirmed_by"]["name"] == "master"
    assert d["governance"]["can"]["reopen_request"]
    db = TestingSessionLocal()
    try:
        assert db.query(ApprovalState).filter(ApprovalState.entity_id == UUID(sid)).count() == 0   # 조회는 쓰지 않는다
    finally:
        db.close()
    # 마스터 본인 요청 → 외부 승인 필요, 다른 마스터도 내부 결정 불가
    r = client.post(f"{_url(sid)}/reopen-requests", headers=t.h["master"], json={"reason": "명백한 오류"})
    assert r.status_code == 201, r.text
    rid = r.json()["governance"]["pending_reopen"]["id"]
    assert client.post(f"{_url(sid)}/reopen-requests/{rid}/decide", headers=t.h["master2"],
                       json={"approve": True}).status_code == 409
    db = TestingSessionLocal()
    tok = set_active_tenant(t.tid)
    try:
        st = db.query(ApprovalState).filter(ApprovalState.entity_id == UUID(sid)).one()
        assert st.legacy_confirmed and st.status == "confirmed"
    finally:
        reset_active_tenant(tok)
        db.close()


def test_sys_admin_only_cannot_submit(client: TestClient) -> None:
    t = T(client, {"admin": ("sys_admin",)})
    sid = _statement(t)
    assert _to(client, t, "admin", sid, "review").status_code == 403


def test_inbox_lists_fs_items(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})
    sid = _statement(t)
    assert _to(client, t, "lead", sid, "review").status_code == 200
    items = client.get("/api/governance/inbox", headers=t.h["master"]).json()
    fs = [i for i in items if i["entity_type"] == "fs_statement"]
    assert [(i["entity_id"], i["action"]) for i in fs] == [(sid, "approve")]
    assert fs[0]["path"] == f"/financial-statements?statement={sid}"
    assert [i for i in client.get("/api/governance/inbox", headers=t.h["lead"]).json()
            if i["entity_type"] == "fs_statement"] == []                          # 요청자는 대기 없음


def test_list_shows_approval_status(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})
    a = _statement(t, 2025)
    b = _statement(t, 2024, final_by="master")
    assert _to(client, t, "lead", a, "review").status_code == 200
    rows = {r["id"]: r["approval_status"] for r in client.get("/api/fs/statements", headers=t.h["lead"]).json()}
    assert (rows[a], rows[b]) == ("review", "confirmed")
