"""통제 ↔ 계정 연결 (ADR-0040) — 자동 매칭 · 초안 수정 · 검토 요청 · 1차/2차 승인 · 커버리지 확정."""
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.services import control_links as cl
from app.services import scoping_coverage as sc
from tests.test_governance import T, template  # noqa: F401
from tests.test_scoping_fs import _fs_2025

C1 = UUID("aaaaaaaa-0000-7000-8000-000000000001")
C2 = UUID("bbbbbbbb-0000-7000-8000-000000000002")


def test_suggest_exact_alias_parent_partial() -> None:
    accts = [
        {"key": "p", "name": "영업수익", "parent_key": None, "fs_account_id": None, "statement_type": "PL"},
        {"key": "c1", "name": "수입수수료", "parent_key": "p", "fs_account_id": None, "statement_type": "PL"},
        {"key": "x", "name": "현금및현금성자산", "parent_key": None, "fs_account_id": None, "statement_type": "BS"},
    ]
    ctrls = [{"id": C1, "code": "C-01", "name": "매출", "related_accounts": "매출, 현금성자산, 전 계정"}]
    got = {(a["key"], kind) for _, a, kind, _ in cl.suggest(ctrls, accts)}
    # 매출 → 매출액 ↔ 영업수익(alias), 하위 수입수수료(parent), 현금성자산 ⊂ 현금및현금성자산(partial)
    assert got == {("p", "alias"), ("c1", "parent"), ("x", "partial")}
    # 반대 방향 부분 일치(계정명 ⊂ 토큰)는 다른 계정이라 잇지 않는다
    wrong = [{"id": C1, "code": "C-01", "name": "x", "related_accounts": "무형자산상각비"}]
    assert cl.suggest(wrong, [{"key": "m", "name": "무형자산", "parent_key": None, "fs_account_id": None,
                               "statement_type": "BS"}]) == []
    # 예외: 괄호 안 보충 표기, 주석 계정
    paren = [{"id": C1, "code": "C-01", "name": "x", "related_accounts": "충당부채(장기근속급여), 법인세비용"}]
    got = {(a["key"], k) for _, a, k, _ in cl.suggest(paren, [
        {"key": "l", "name": "장기근속급여", "parent_key": None, "fs_account_id": None, "statement_type": "BS"},
        {"key": "n", "name": "29. 법인세", "parent_key": None, "fs_account_id": None, "statement_type": "NOTE"}])}
    assert got == {("l", "partial"), ("n", "partial")}


@pytest.fixture()
def env(client: TestClient, monkeypatch):
    t = T(client, {"staff": ("icfr_staff",), "lead": ("icfr_lead",), "master": ("icfr_manager",)})
    _fs_2025(client, t.h["master"])
    assert client.post("/api/scoping", headers=t.h["master"],
                       json={"fiscal_year": 2026, "source": "financial_statements"}).status_code == 201
    board = client.get("/api/control-links/board", headers=t.h["staff"]).json()
    parent = next(a for a in board["accounts"] if a["has_children"] and a["depth"] >= 1)
    child = next(a for a in board["accounts"] if a["parent_key"] == parent["key"])
    other = next(a for a in board["accounts"] if a["key"] not in (parent["key"], child["key"])
                 and not a["has_children"] and a["statement_type"] == "BS")
    fake = [{"id": C1, "code": "C-01", "name": "통제1", "process_code": "P1", "is_key_control": True,
             "related_accounts": parent["name"]},
            {"id": C2, "code": "C-02", "name": "통제2", "process_code": "P1", "is_key_control": False,
             "related_accounts": "N/A"}]
    monkeypatch.setattr(cl, "resolve_controls", lambda db: fake)
    monkeypatch.setattr(cl, "resolve_processes", lambda db: [{"code": "P1", "name": "프로세스1"}])
    monkeypatch.setattr(sc, "resolve_controls", lambda db: fake)
    return t, parent, child, other


def _links(client, t):
    return client.get("/api/control-links/board", headers=t.h["staff"]).json()["links"]


def test_auto_draft_edit_submit_two_step_approval(client: TestClient, env) -> None:
    t, parent, child, other = env
    r = client.post("/api/control-links/auto", headers=t.h["staff"])
    assert r.status_code == 200 and r.json()["added"] >= 2
    links = {(lk["control_id"], lk["account_key"]): lk for lk in _links(client, t)}
    assert links[(str(C1), parent["key"])]["match_kind"] == "exact"
    assert links[(str(C1), child["key"])]["match_kind"] == "parent"
    # 실무자가 자동 결과 하나를 뺀다 → 다시 자동 매칭해도 들어오지 않는다
    cid = links[(str(C1), child["key"])]["id"]
    assert client.delete(f"/api/control-links/links/{cid}", headers=t.h["staff"]).json()["result"] == "dismissed"
    assert client.post("/api/control-links/auto", headers=t.h["staff"]).json()["added"] == 0
    # 드래그로 수동 연결
    r = client.post("/api/control-links/links", headers=t.h["staff"],
                    json={"control_id": str(C2), "account_key": other["key"]})
    assert r.status_code == 200 and r.json()["state"] == "draft"
    # 검토 요청 → 제안 묶음
    pid = client.post("/api/control-links/submit", headers=t.h["staff"], json={"note": "1차 연결"}).json()["proposal_id"]
    assert all(lk["state"] == "review" for lk in _links(client, t))
    assert client.post("/api/control-links/submit", headers=t.h["staff"], json={}).status_code == 409
    d = client.get(f"/api/proposals/{pid}", headers=t.h["lead"]).json()
    assert d["kind"] == "control_link" and d["requested_by"]["name"] and d["items"][0]["control_code"]
    # 실무자는 결정 못 함, 책임관리자가 항목별 결정(수동 연결은 반려)
    first = d["items"][0]["id"]
    assert client.post(f"/api/proposals/{pid}/items/{first}/decide", headers=t.h["staff"],
                       json={"decision": "accepted"}).status_code == 409
    c2 = next(it for it in d["items"] if it["control_code"] == "C-02")
    assert client.post(f"/api/proposals/{pid}/items/{c2['id']}/decide", headers=t.h["lead"],
                       json={"decision": "rejected"}).status_code == 200
    r = client.post(f"/api/proposals/{pid}/decide-pending", headers=t.h["lead"], json={"decision": "accepted"})
    assert r.status_code == 200 and r.json()["counts"].get("pending", 0) == 0
    assert client.post(f"/api/proposals/{pid}/review-done", headers=t.h["lead"], json={}).status_code == 200
    r = client.post(f"/api/proposals/{pid}/approve", headers=t.h["master"], json={})
    assert r.status_code == 200, r.text
    n_c1 = sum(1 for it in d["items"] if it["control_code"] == "C-01")
    assert r.json()["result"]["linked"] == n_c1 and r.json()["result"]["rejected"] == 1
    states = {(lk["control_id"], lk["account_key"]): lk["state"] for lk in _links(client, t)}
    assert states[(str(C1), parent["key"])] == "active" and set(states.values()) == {"active"}
    assert all(cid == str(C1) for cid, _ in states)   # 반려된 수동 연결은 보드에서 빠진다


def test_requester_cannot_approve_and_return_reverts(client: TestClient, env) -> None:
    t, parent, _, _ = env
    client.post("/api/control-links/links", headers=t.h["lead"], json={"control_id": str(C2), "account_key": parent["key"]})
    pid = client.post("/api/control-links/submit", headers=t.h["lead"], json={}).json()["proposal_id"]
    d = client.get(f"/api/proposals/{pid}", headers=t.h["lead"]).json()
    assert d["can"]["decide"] is False and "자기 승인" in d["can"]["why"]["review"]
    assert client.post(f"/api/proposals/{pid}/items/{d['items'][0]['id']}/decide", headers=t.h["lead"],
                       json={"decision": "accepted"}).status_code == 409


def test_return_reverts_to_draft_and_remove_active(client: TestClient, env) -> None:
    t, parent, _, _ = env
    client.post("/api/control-links/links", headers=t.h["staff"], json={"control_id": str(C2), "account_key": parent["key"]})
    pid = client.post("/api/control-links/submit", headers=t.h["staff"], json={}).json()["proposal_id"]
    assert client.post(f"/api/proposals/{pid}/return", headers=t.h["lead"], json={"reason": "다시"}).status_code == 200
    lk = _links(client, t)[0]
    assert lk["state"] == "draft"
    # 다시 요청 → 승인 → 활성 → 해제 초안 → 승인 → 삭제
    pid = client.post("/api/control-links/submit", headers=t.h["staff"], json={}).json()["proposal_id"]
    it = client.get(f"/api/proposals/{pid}", headers=t.h["lead"]).json()["items"][0]["id"]
    client.post(f"/api/proposals/{pid}/items/{it}/decide", headers=t.h["lead"], json={"decision": "accepted"})
    client.post(f"/api/proposals/{pid}/review-done", headers=t.h["lead"], json={})
    client.post(f"/api/proposals/{pid}/approve", headers=t.h["master"], json={})
    lk = _links(client, t)[0]
    assert lk["state"] == "active"
    assert client.delete(f"/api/control-links/links/{lk['id']}", headers=t.h["staff"]).json()["result"] == "remove_draft"
    pid = client.post("/api/control-links/submit", headers=t.h["staff"], json={}).json()["proposal_id"]
    it = client.get(f"/api/proposals/{pid}", headers=t.h["lead"]).json()["items"][0]
    assert it["action"] == "link_remove"
    client.post(f"/api/proposals/{pid}/items/{it['id']}/decide", headers=t.h["lead"], json={"decision": "accepted"})
    client.post(f"/api/proposals/{pid}/review-done", headers=t.h["lead"], json={})
    assert client.post(f"/api/proposals/{pid}/approve", headers=t.h["master"], json={}).json()["result"]["unlinked"] == 1
    assert _links(client, t) == []


def test_coverage_uses_active_links(client: TestClient, env) -> None:
    t, parent, child, _ = env
    sid = client.get("/api/scoping", headers=t.h["master"]).json()[0]["id"]
    # 확정 근거가 없으면 추정
    cov = client.get(f"/api/scoping/{sid}/coverage", headers=t.h["master"]).json()
    assert all(r["basis"] == "estimated" for r in cov["accounts"]) and cov["linked_accounts"] == 0
    for a in (parent, child):
        client.post("/api/control-links/links", headers=t.h["staff"], json={"control_id": str(C2), "account_key": a["key"]})
    pid = client.post("/api/control-links/submit", headers=t.h["staff"], json={}).json()["proposal_id"]
    for it in client.get(f"/api/proposals/{pid}", headers=t.h["lead"]).json()["items"]:
        client.post(f"/api/proposals/{pid}/items/{it['id']}/decide", headers=t.h["lead"], json={"decision": "accepted"})
    client.post(f"/api/proposals/{pid}/review-done", headers=t.h["lead"], json={})
    client.post(f"/api/proposals/{pid}/approve", headers=t.h["master"], json={})
    cov = client.get(f"/api/scoping/{sid}/coverage", headers=t.h["master"]).json()
    linked = [r for r in cov["accounts"] if r["basis"] == "linked"]
    sig_keys = {a["key"] for a in client.get("/api/control-links/board", headers=t.h["staff"]).json()["accounts"]
                if a["significant"] == "Y"}
    expected = len({parent["key"], child["key"]} & sig_keys)
    assert len(linked) == expected == cov["linked_accounts"]
    assert all(r["controls"][0]["code"] == "C-02" for r in linked)
