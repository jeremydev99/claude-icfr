"""평가 회차 최종승인 결재 (ADR-0038 2-4) + 미비점 일괄 결재.

마감자 ≠ 승인자, 마감자 외 마스터가 없으면 외부 승인 증빙, 미확정 미비점은 경고만, 재오픈 없음, 이전 방식 승인.
"""
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.tenant_context import reset_active_tenant, set_active_tenant
from app.models.assessment import AssessmentCycle
from app.models.rcm_baseline import (
    BaselineControl,
    BaselineProcess,
    BaselineRisk,
    BaselineSubProcess,
)
from app.models.role_assignment import RoleAssignment
from app.services import approval_flow
from tests.conftest import TestingSessionLocal
from tests.test_governance import T

CY = "/api/assessment/cycles"
DEF = "/api/remediation/deficiencies"


@pytest.fixture(autouse=True)
def no_minio(monkeypatch):
    stored = {}
    monkeypatch.setattr(approval_flow, "upload_object", lambda key, data, mime: stored.__setitem__(key, data))
    return stored


def _setup(t: T, assessor: str) -> None:
    """테넌트 `t` 에 연간 통제 1개 + `assessor` 를 그 통제의 평가자로."""
    db = TestingSessionLocal()
    tok = set_active_tenant(t.tid)
    try:
        tag = uuid4().hex[:5]
        p = BaselineProcess(code=f"CA{tag}-P", name="P")
        db.add(p)
        db.flush()
        sp = BaselineSubProcess(code=f"CA{tag}-SP", name="SP", process_id=p.id)
        db.add(sp)
        db.flush()
        r = BaselineRisk(code=f"CA{tag}-R", description="R", assessment_level="LR", sub_process_id=sp.id)
        db.add(r)
        db.flush()
        c = BaselineControl(code=f"CA{tag}-C", name="C", risk_id=r.id, assessment_frequency="annual")
        db.add(c)
        db.flush()
        db.add(RoleAssignment(scope="control", target_id=c.id, role_name="assessor", user_id=UUID(t.uid[assessor])))
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()


def _closed_cycle(client, t: T, assessor: str) -> str:
    r = client.post(CY, headers=t.h[assessor], json={"kind": "operation", "frequency": "annual",
                                                     "name": f"2026 운영평가 {uuid4().hex[:4]}",
                                                     "fiscal_year": 2026, "period_index": 1})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = client.post(f"{CY}/{cid}/close", headers=t.h[assessor], json={"incomplete_reason": "기한 내 미완"})
    assert r.status_code == 200, r.text
    return cid


def test_closer_cannot_approve_other_master_can(client: TestClient) -> None:
    t = T(client, {"closer": ("icfr_manager",), "master2": ("icfr_manager",)})
    _setup(t, "closer")
    cid = _closed_cycle(client, t, "closer")
    g = client.get(f"{CY}/{cid}/governance", headers=t.h["closer"]).json()
    assert not g["can_approve"] and "자기 승인 금지" in g["why"]["approve"] and g["incomplete_count"] == 1
    assert client.post(f"{CY}/{cid}/approve", headers=t.h["closer"]).status_code == 409
    inbox = [i for i in client.get("/api/governance/inbox", headers=t.h["master2"]).json()
             if i["entity_type"] == "assessment_cycle"]
    assert [(i["entity_id"], i["action"]) for i in inbox] == [(cid, "approve")]
    assert not [i for i in client.get("/api/governance/inbox", headers=t.h["closer"]).json()
                if i["entity_type"] == "assessment_cycle"]
    r = client.post(f"{CY}/{cid}/approve", headers=t.h["master2"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved" and r.json()["approved_by_name"] == "master2"
    acts = [e["action"] for e in client.get(f"{CY}/{cid}/governance-events", headers=t.h["closer"]).json()]
    assert acts == ["approve", "cycle_close"]
    g = client.get(f"{CY}/{cid}/governance", headers=t.h["closer"]).json()
    assert not g["legacy_approved"] and not g["can_approve"]
    assert client.post(f"{CY}/{cid}/approve", headers=t.h["master2"]).status_code == 409   # 재오픈·재승인 없음


def test_only_master_closer_uses_external_approval(client: TestClient, no_minio) -> None:
    t = T(client, {"closer": ("icfr_manager",), "staff": ("icfr_staff",)})
    _setup(t, "closer")
    cid = _closed_cycle(client, t, "closer")
    g = client.get(f"{CY}/{cid}/governance", headers=t.h["staff"]).json()
    assert g["can_external_approve"] and not g["can_approve"]
    assert client.post(f"{CY}/{cid}/approve", headers=t.h["closer"]).status_code == 409
    form = {"approver_body": "board", "approved_on": "2027-02-20", "reference": "제3차 이사회"}
    assert client.post(f"{CY}/{cid}/external-approval", headers=t.h["staff"], data=form,
                       files={"files": ("", b"", "application/pdf")}).status_code == 422          # 증빙 필수
    r = client.post(f"{CY}/{cid}/external-approval", headers=t.h["staff"], data=form,
                    files={"files": ("minutes.pdf", b"%PDF", "application/pdf")})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["cycle"]["status"] == "approved" and d["cycle"]["approved_by_id"] is None
    assert d["external_approvals"][0]["reference"] == "제3차 이사회" and not d["legacy_approved"]
    assert next(iter(no_minio)).split("/")[2] == "assessment_cycle"


def test_external_not_allowed_when_other_master_exists(client: TestClient) -> None:
    t = T(client, {"closer": ("icfr_manager",), "master2": ("icfr_manager",)})
    _setup(t, "closer")
    cid = _closed_cycle(client, t, "closer")
    r = client.post(f"{CY}/{cid}/external-approval", headers=t.h["closer"],
                    data={"approver_body": "ceo", "approved_on": "2027-02-20"},
                    files={"files": ("a.pdf", b"%PDF", "application/pdf")})
    assert r.status_code == 409


def test_unconfirmed_deficiencies_warn_but_do_not_block(client: TestClient) -> None:
    t = T(client, {"assessor": (), "master": ("icfr_manager",)})
    _setup(t, "assessor")
    cid = _closed_cycle(client, t, "assessor")
    assert client.post(DEF, headers=t.h["master"], json={"code": f"D-{uuid4().hex[:5]}", "severity": "low",
                                                         "description": "x", "fiscal_year": 2026}).status_code == 201
    g = client.get(f"{CY}/{cid}/governance", headers=t.h["master"]).json()
    assert g["fiscal_year"] == 2026 and g["unconfirmed_deficiencies"] == 1 and g["can_approve"]
    assert client.post(f"{CY}/{cid}/approve", headers=t.h["master"]).status_code == 200


def test_legacy_approved_cycle(client: TestClient) -> None:
    t = T(client, {"assessor": (), "master": ("icfr_manager",)})
    _setup(t, "assessor")
    cid = _closed_cycle(client, t, "assessor")
    db = TestingSessionLocal()
    tok = set_active_tenant(t.tid)
    try:   # 2-4 이전 방식(마감자=승인자 가능, 이력 없음)으로 승인된 회차를 흉내낸다
        c = db.get(AssessmentCycle, UUID(cid))
        c.status, c.approved_by_id = "approved", c.closed_by_id
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()
    g = client.get(f"{CY}/{cid}/governance", headers=t.h["master"]).json()
    assert g["legacy_approved"] and not g["can_approve"]


def test_deficiency_bulk_transition(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})
    ids = []
    for i, concl in enumerate(["단순 미비점", "유의적 미비점", None]):
        body = {"code": f"B{i}-{uuid4().hex[:5]}", "severity": "low", "description": "x", "fiscal_year": 2026}
        if concl:
            body["final_conclusion"] = concl
        ids.append(client.post(DEF, headers=t.h["lead"], json=body).json()["id"])
    missing = str(uuid4())
    r = client.post(f"{DEF}/bulk-transition", headers=t.h["lead"],
                    json={"ids": ids + [missing, ids[0]], "to_status": "review"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert (b["succeeded"], b["failed"]) == (2, 2)                                  # 결론 없는 1건 + 없는 id 1건
    by = {i["id"]: i for i in b["items"]}
    assert by[ids[0]]["ok"] and by[ids[0]]["approval_status"] == "review"
    assert not by[ids[2]]["ok"] and "최종 결론" in by[ids[2]]["detail"]
    assert not by[missing]["ok"]
    # 일괄 승인 — 요청자 본인(lead)은 승인권이 없어 전부 실패, 마스터는 2건 확정
    assert client.post(f"{DEF}/bulk-transition", headers=t.h["lead"],
                       json={"ids": ids[:2], "to_status": "confirmed", "reason": "x"}).json()["succeeded"] == 0
    r = client.post(f"{DEF}/bulk-transition", headers=t.h["master"],
                    json={"ids": ids, "to_status": "confirmed", "reason": "일괄 확정"}).json()
    assert r["succeeded"] == 2 and r["failed"] == 1
    assert client.get(f"{DEF}/{ids[0]}", headers=t.h["lead"]).json()["confirmed_at"]
