"""제안 결재 — AI 초안 → 책임관리자 1차(항목별) → 마스터 2차 → 반영 (services/proposals.py)."""
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.audit_context import system_actor
from app.core.tenant_context import reset_active_tenant, set_active_tenant
from app.models.proposal import KIND_FS_TEMPLATE_LINK
from app.services import fs_template_match as m
from app.services import proposals as psvc
from tests.conftest import TestingSessionLocal
from tests.test_governance import T, template  # noqa: F401 — 템플릿 적재 fixture 재사용
from tests.test_scoping_fs import _fs_2025


def _setup(client: TestClient):
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",), "master2": ("icfr_manager",)})
    _fs_2025(client, t.h["master"])
    r = client.post("/api/scoping", headers=t.h["master"], json={"fiscal_year": 2026, "source": "financial_statements"})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    db = TestingSessionLocal()
    tok = set_active_tenant(t.tid)
    try:
        tpl = m.get_template(db, None, None)
        bs = m.matches(db, "BS", None, None)
        leaves = [a for a in bs["accounts"] if not a["is_subtotal"] and not a["link"]][:2]
        tmpl = {x["name"]: x["id"] for x in bs["template_accounts"]}
        items = [dict(account_id=a["account_id"], statement_type="BS", account_name=a["name"], group_label=None,
                      action="link", template_account_id=tmpl["매출채권"], template_name="매출채권",
                      rationale="테스트 근거") for a in leaves]
        with system_actor("system:claude-proposal"):
            p = psvc.create(db, kind=KIND_FS_TEMPLATE_LINK, title="연결 제안 테스트", summary=None,
                            proposed_by="system:claude-proposal", items=items, template=tpl, scoping_id=UUID(sid))
            db.commit()
        return t, str(p.id), sid, tmpl
    finally:
        reset_active_tenant(tok)
        db.close()


def test_two_step_approval_applies_links_and_reloads_scoping(client: TestClient) -> None:
    t, pid, sid, tmpl = _setup(client)
    d = client.get(f"/api/proposals/{pid}", headers=t.h["lead"]).json()
    assert d["status"] == "pending_review" and d["can"]["decide"] and not d["can"]["review_done"]
    # 마스터는 1차 결정 불가
    i0, i1 = d["items"][0]["id"], d["items"][1]["id"]
    assert client.post(f"/api/proposals/{pid}/items/{i0}/decide", headers=t.h["master"],
                       json={"decision": "accepted"}).status_code == 409
    client.post(f"/api/proposals/{pid}/items/{i0}/decide", headers=t.h["lead"], json={"decision": "accepted"})
    r = client.post(f"/api/proposals/{pid}/items/{i1}/decide", headers=t.h["lead"],
                    json={"decision": "modified", "template_account_id": str(tmpl["미수금"]), "note": "미수금이 맞음"})
    assert r.json()["items"][1]["final_template_name"] == "미수금"
    # 1차 검토 완료 → 1차 검토자는 2차 불가, 마스터 2차 → 반영
    assert client.post(f"/api/proposals/{pid}/review-done", headers=t.h["lead"], json={}).json()["status"] == "reviewed"
    assert client.post(f"/api/proposals/{pid}/approve", headers=t.h["lead"], json={}).status_code == 409
    r = client.post(f"/api/proposals/{pid}/approve", headers=t.h["master"], json={"reason": "확인"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "approved" and d["result"]["linked"] == 2 and d["result"]["scoping_reloaded"] is True
    ev = [e["action"] for e in client.get(f"/api/proposals/{pid}/events", headers=t.h["lead"]).json()]
    assert ev[0] == "proposal_approve" and "proposal_create" in ev and ev.count("proposal_item_decide") == 2


def test_review_needs_all_items_and_return_closes(client: TestClient) -> None:
    t, pid, _, _ = _setup(client)
    d = client.get(f"/api/proposals/{pid}", headers=t.h["lead"]).json()
    client.post(f"/api/proposals/{pid}/items/{d['items'][0]['id']}/decide", headers=t.h["lead"],
                json={"decision": "rejected"})
    assert client.post(f"/api/proposals/{pid}/review-done", headers=t.h["lead"], json={}).status_code == 409
    assert client.post(f"/api/proposals/{pid}/return", headers=t.h["lead"], json={"reason": ""}).status_code == 409
    assert client.post(f"/api/proposals/{pid}/return", headers=t.h["lead"],
                       json={"reason": "다시 제안"}).json()["status"] == "returned"


def test_inbox_routes_to_lead_then_master(client: TestClient) -> None:
    t, pid, _, _ = _setup(client)
    lead_inbox = client.get("/api/governance/inbox", headers=t.h["lead"]).json()
    assert any(i["entity_id"] == pid and i["action"] == "proposal_review" for i in lead_inbox)
    assert not any(i["entity_id"] == pid for i in client.get("/api/governance/inbox", headers=t.h["master"]).json())
