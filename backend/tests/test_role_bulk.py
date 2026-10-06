"""역할 일괄 배정 (2026-10-06) — 표 조회, 프로세스 기본값·통제 예외 일괄 적용, 지우기, 겸직 사유·정책 금지."""
from fastapi.testclient import TestClient

from tests.test_org_roles import _chain, _make_user, org_ctx  # noqa: F401 — fixture 재사용


def _matrix_control(client, h, cid):
    m = client.get("/api/org/role-matrix", headers=h).json()
    return m, next(c for c in m["controls"] if c["id"] == str(cid))


def test_bulk_process_default_and_control_override(client: TestClient, org_ctx) -> None:  # noqa: F811
    h, db = org_ctx
    a = str(_make_user(db, "bulk-a@acme.example", "가나"))
    b = str(_make_user(db, "bulk-b@acme.example", "다라"))
    pid, cid = _chain(db, "BK1")
    r = client.post("/api/org/assignments/bulk", headers=h, json={"changes": [
        {"scope": "process", "target_id": str(pid), "role_name": "control_owner", "user_id": a},
        {"scope": "process", "target_id": str(pid), "role_name": "assessor", "user_id": b},
    ]})
    assert r.status_code == 200, r.text
    assert r.json()["applied"] == 2
    m, c = _matrix_control(client, h, cid)
    roles = {x["role_name"]: x for x in c["roles"]}
    assert roles["control_owner"]["user_name"] == "가나" and roles["control_owner"]["source"] == "process"
    proc = next(p for p in m["processes"] if p["id"] == str(pid))
    assert proc["roles"]["assessor"]["user_name"] == "다라"
    assert any(u["name"] == "가나" for u in m["users"])
    # 통제 예외로 평가자 교체 → 다시 지우면 프로세스 기본값으로 돌아간다
    c3 = str(_make_user(db, "bulk-e@acme.example", "마바"))
    r = client.post("/api/org/assignments/bulk", headers=h, json={"changes": [
        {"scope": "control", "target_id": str(cid), "role_name": "assessor", "user_id": c3}]})
    assert r.status_code == 200, r.text
    _, c = _matrix_control(client, h, cid)
    assert {x["role_name"]: x for x in c["roles"]}["assessor"]["source"] == "control"
    client.post("/api/org/assignments/bulk", headers=h, json={"changes": [
        {"scope": "control", "target_id": str(cid), "role_name": "assessor", "user_id": None}]})
    _, c = _matrix_control(client, h, cid)
    assessor = {x["role_name"]: x for x in c["roles"]}["assessor"]
    assert assessor["source"] == "process" and assessor["user_name"] == "다라"


def test_bulk_conflict_needs_reason_then_records(client: TestClient, org_ctx) -> None:  # noqa: F811
    h, db = org_ctx
    a = str(_make_user(db, "bulk-c@acme.example", "겸직"))
    pid, cid = _chain(db, "BK2")
    body = {"changes": [
        {"scope": "process", "target_id": str(pid), "role_name": "control_owner", "user_id": a},
        {"scope": "process", "target_id": str(pid), "role_name": "assessor", "user_id": a}]}
    r = client.post("/api/org/assignments/bulk", headers=h, json=body)
    assert r.status_code == 409
    d = r.json()["detail"]
    assert "사유" in d["message"] and d["conflicts"][0]["control_code"] == "ORBK2-C"
    # 실패하면 아무것도 저장하지 않는다
    _, c = _matrix_control(client, h, cid)
    assert all(x["user_id"] is None for x in c["roles"] if x["role_name"] != "dept_approver")
    r = client.post("/api/org/assignments/bulk", headers=h, json={**body, "conflict_reason": "인원 부족, 상급자 검토로 보완"})
    assert r.status_code == 200 and r.json()["acknowledged"][0]["control_code"] == "ORBK2-C"
    _, c = _matrix_control(client, h, cid)
    assert "assessor=control_owner" in c["conflicts"]


def test_bulk_remove_and_validation(client: TestClient, org_ctx) -> None:  # noqa: F811
    h, db = org_ctx
    a = str(_make_user(db, "bulk-d@acme.example", "지움"))
    _, cid = _chain(db, "BK3")
    client.post("/api/org/assignments/bulk", headers=h, json={"changes": [
        {"scope": "control", "target_id": str(cid), "role_name": "control_owner", "user_id": a}]})
    r = client.post("/api/org/assignments/bulk", headers=h, json={"changes": [
        {"scope": "control", "target_id": str(cid), "role_name": "control_owner", "user_id": None}]})
    assert r.status_code == 200 and r.json()["removed"] == 1
    bad = client.post("/api/org/assignments/bulk", headers=h, json={"changes": [
        {"scope": "control", "target_id": "aaaaaaaa-0000-7000-8000-000000000009", "role_name": "assessor", "user_id": a}]})
    assert bad.status_code == 409 and "대상" in bad.json()["detail"]["message"]
    assert client.post("/api/org/assignments/bulk", headers=h, json={"changes": []}).status_code == 422
