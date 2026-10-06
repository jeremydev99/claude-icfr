"""통제 변경 결재 (2026-10-06) — 임시저장 → 조직장 → 내부회계 담당자 일괄 상신 → 내부회계관리자 → 반영."""
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.audit_context import system_actor
from app.core.tenant_context import reset_active_tenant, set_active_tenant
from app.models.org import Department, UserDepartment
from app.models.rcm_baseline import (
    BaselineControl,
    BaselineProcess,
    BaselineRisk,
    BaselineSubProcess,
)
from app.models.role_assignment import RoleAssignment
from tests.conftest import TestingSessionLocal
from tests.test_governance import T, template  # noqa: F401


@pytest.fixture()
def env(client: TestClient):
    t = T(client, {"owner": (), "head": (), "staff": ("icfr_staff",), "master": ("icfr_manager",)})
    db = TestingSessionLocal()
    tok = set_active_tenant(t.tid)
    try:
        with system_actor("system:test"):
            p = BaselineProcess(code="CC-P", name="P")
            db.add(p)
            db.flush()
            sp = BaselineSubProcess(code="CC-SP", name="SP", process_id=p.id)
            db.add(sp)
            db.flush()
            r = BaselineRisk(code="CC-R", description="R", assessment_level="LR", sub_process_id=sp.id)
            db.add(r)
            db.flush()
            c = BaselineControl(code="CC-C1", name="원래 통제명", risk_id=r.id, owner_name="담당")
            db.add(c)
            d = Department(name="재무팀", manager_id=UUID(t.uid["head"]))
            db.add(d)
            db.flush()
            db.add(UserDepartment(user_id=UUID(t.uid["owner"]), department_id=d.id, is_primary=True))
            db.add(RoleAssignment(scope="control", target_id=c.id, role_name="control_owner", user_id=UUID(t.uid["owner"])))
            db.commit()
            cid = str(c.id)
    finally:
        reset_active_tenant(tok)
        db.close()
    return t, cid


def test_full_flow_draft_dept_batch_admin_apply(client: TestClient, env) -> None:
    t, cid = env
    # 내부회계관리자가 있는 회사 — 담당자는 바로 반영할 수 없다
    assert client.patch(f"/api/rcm/controls/{cid}", headers=t.h["owner"], json={"name": "x"}).status_code == 403
    assert client.get(f"/api/rcm-changes/control/{cid}", headers=t.h["owner"]).json()["direct_edit"] is False
    # 임시저장 → 상신(조직장 = 주 소속 부서장)
    r = client.put(f"/api/rcm-changes/control/{cid}", headers=t.h["owner"], json={"changes": {"name": "새 통제명"}, "note": "명칭 정비"})
    assert r.status_code == 200 and r.json()["status"] == "draft" and r.json()["before"]["name"] == "원래 통제명"
    ch = r.json()["id"]
    assert client.put(f"/api/rcm-changes/control/{cid}", headers=t.h["staff"], json={"changes": {"name": "y"}}).status_code == 409
    d = client.post(f"/api/rcm-changes/{ch}/submit", headers=t.h["owner"]).json()
    assert d["status"] == "dept_review" and d["dept_approver"] == "head"
    # 조직장: 반려는 사유 필수, 승인 → 내부회계 대기함
    assert client.post(f"/api/rcm-changes/{ch}/dept-approve", headers=t.h["staff"], json={}).status_code == 409
    assert client.post(f"/api/rcm-changes/{ch}/dept-reject", headers=t.h["head"], json={}).status_code == 409
    assert client.post(f"/api/rcm-changes/{ch}/dept-approve", headers=t.h["head"], json={"note": "확인"}).json()["status"] == "dept_approved"
    ov = client.get("/api/rcm-changes", headers=t.h["staff"]).json()
    assert [x["id"] for x in ov["queue"]] == [ch]
    # 내부회계 담당자 일괄 상신 → 내부회계관리자 결재 → 반영
    assert client.post("/api/rcm-changes/batches", headers=t.h["owner"], json={"change_ids": [ch]}).status_code == 409
    bid = client.post("/api/rcm-changes/batches", headers=t.h["staff"], json={"change_ids": [ch], "note": "10월 묶음"}).json()["id"]
    body = {"decisions": [{"id": ch, "approve": True}]}
    assert client.post(f"/api/rcm-changes/batches/{bid}/decide", headers=t.h["staff"], json=body).status_code == 409
    r = client.post(f"/api/rcm-changes/batches/{bid}/decide", headers=t.h["master"], json=body)
    assert r.status_code == 200 and r.json() == {"applied": 1, "rejected": 0}
    assert client.get(f"/api/rcm/controls/{cid}", headers=t.h["owner"]).json()["name"] == "새 통제명"
    assert client.get(f"/api/rcm-changes/control/{cid}", headers=t.h["owner"]).json()["change"] is None


def test_admin_reject_returns_to_author_and_self_batch_blocked(client: TestClient, env) -> None:
    t, cid = env
    ch = client.put(f"/api/rcm-changes/control/{cid}", headers=t.h["owner"], json={"changes": {"description": "새 설명"}}).json()["id"]
    client.post(f"/api/rcm-changes/{ch}/submit", headers=t.h["owner"])
    client.post(f"/api/rcm-changes/{ch}/dept-approve", headers=t.h["head"], json={})
    bid = client.post("/api/rcm-changes/batches", headers=t.h["master"], json={"change_ids": [ch]}).json()["id"]
    assert "자기 승인" in client.post(f"/api/rcm-changes/batches/{bid}/decide", headers=t.h["master"],
                                     json={"decisions": [{"id": ch, "approve": True}]}).json()["detail"]
    # 상신자 본인에게는 결재 버튼이 보이지 않는다
    t2_batch = client.get("/api/rcm-changes", headers=t.h["staff"]).json()["batches"][0]
    assert t2_batch["id"] == bid and t2_batch["can_decide"] is False


def test_head_as_author_skips_dept_and_reject_path(client: TestClient, env) -> None:
    t, cid = env
    ch = client.put(f"/api/rcm-changes/control/{cid}", headers=t.h["head"], json={"changes": {"objective": "목적"}}).json()["id"]
    d = client.post(f"/api/rcm-changes/{ch}/submit", headers=t.h["head"]).json()
    # 조직장(통제책임자의 부서장)이 직접 쓴 변경 — 본인 결재를 건너뛴다
    assert d["status"] == "dept_approved" and d["dept_skipped"] == "작성자가 조직장"
    bid = client.post("/api/rcm-changes/batches", headers=t.h["staff"], json={"change_ids": [ch]}).json()["id"]
    assert client.post(f"/api/rcm-changes/batches/{bid}/decide", headers=t.h["master"],
                       json={"decisions": [{"id": ch, "approve": False}]}).status_code == 409   # 반려 사유 필요
    r = client.post(f"/api/rcm-changes/batches/{bid}/decide", headers=t.h["master"],
                    json={"decisions": [{"id": ch, "approve": False, "note": "목적 문구 보완"}]})
    assert r.json() == {"applied": 0, "rejected": 1}
    mine = client.get("/api/rcm-changes", headers=t.h["head"]).json()["mine"][0]
    assert mine["status"] == "rejected" and mine["rejected_by"] == "admin" and mine["admin_note"] == "목적 문구 보완"
    # 반려된 변경은 고쳐서 다시 임시저장 가능
    assert client.put(f"/api/rcm-changes/control/{cid}", headers=t.h["head"], json={"changes": {"objective": "목적 2"}}).json()["status"] == "draft"


def test_bulk_draft_and_submit_per_control(client: TestClient, env) -> None:
    t, cid = env
    # 먼저 다른 항목을 임시저장해 두고, 일괄 변경이 그것을 지우지 않는지(merge)
    client.put(f"/api/rcm-changes/control/{cid}", headers=t.h["owner"], json={"changes": {"objective": "목적"}})
    r = client.post("/api/rcm-changes/bulk", headers=t.h["owner"],
                    json={"control_ids": [cid, "aaaaaaaa-0000-7000-8000-00000000000b"], "changes": {"owner_name": "새 담당"}, "submit": True})
    d = r.json()
    assert r.status_code == 200 and len(d["ok"]) == 1 and len(d["failed"]) == 1
    assert d["ok"][0]["status"] == "dept_review"
    mine = client.get("/api/rcm-changes", headers=t.h["owner"]).json()["mine"][0]
    assert mine["changes"] == {"objective": "목적", "owner_name": "새 담당"}
    # 바로 반영과 같은 값 검증 — 허용값 밖이면 422
    bad = client.post("/api/rcm-changes/bulk", headers=t.h["owner"], json={"control_ids": [cid], "changes": {"frequency": "S"}})
    assert bad.status_code == 422
