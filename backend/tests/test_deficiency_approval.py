"""미비점 평가 결재 (ADR-0038 2-3) — 확정자 위조 차단, 결재선, 검토 중·확정 잠금, 재오픈 없음, 이전 방식 확정."""
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.tenant_context import reset_active_tenant, set_active_tenant
from app.models.remediation import Deficiency
from app.services import approval_flow
from tests.conftest import TestingSessionLocal
from tests.test_governance import T

BASE = "/api/remediation/deficiencies"


@pytest.fixture(autouse=True)
def no_minio(monkeypatch):
    stored = {}
    monkeypatch.setattr(approval_flow, "upload_object", lambda key, data, mime: stored.__setitem__(key, data))
    return stored


def _new(client, t: T, who: str = "staff", **kw) -> str:
    body = {"code": f"D-{uuid4().hex[:6]}", "severity": "medium", "description": "증빙 누락", "fiscal_year": 2026, **kw}
    r = client.post(BASE, headers=t.h[who], json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _to(client, t, who, did, to, reason=None):
    return client.post(f"{BASE}/{did}/transition", headers=t.h[who], json={"to_status": to, "reason": reason})


def test_confirmed_fields_cannot_be_written_directly(client: TestClient) -> None:
    """예전 구멍 — PATCH 로 확정자·확정일을 적을 수 있었다. 이제 그 칸은 무시된다."""
    t = T(client, {"staff": ("icfr_staff",), "master": ("icfr_manager",)})
    did = _new(client, t)
    r = client.patch(f"{BASE}/{did}", headers=t.h["staff"],
                     json={"confirmed_by_id": t.uid["master"], "confirmed_at": "2026-01-01T00:00:00Z"})
    assert r.status_code == 200, r.text
    assert r.json()["confirmed_by_id"] is None and r.json()["confirmed_at"] is None
    assert r.json()["approval_status"] == "draft"


def test_submit_requires_conclusion_then_lead_master_path(client: TestClient) -> None:
    t = T(client, {"staff": ("icfr_staff",), "lead": ("icfr_lead",), "master": ("icfr_manager",)})
    did = _new(client, t)
    assert _to(client, t, "staff", did, "review").status_code == 422             # 결론 없음
    assert client.patch(f"{BASE}/{did}", headers=t.h["staff"],
                        json={"final_conclusion": "유의적 미비점 — 보완 필요"}).status_code == 200
    r = _to(client, t, "staff", did, "review")
    assert r.status_code == 200, r.text
    assert r.json()["governance"]["review_path"] == "lead_then_master"
    assert _to(client, t, "master", did, "confirmed", "먼저").status_code == 409    # 검토 전
    assert client.post(f"{BASE}/{did}/review", headers=t.h["lead"], json={"action": "done"}).status_code == 200
    r = _to(client, t, "master", did, "confirmed", "확정")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["deficiency"]["approval_status"] == "confirmed" and not d["legacy_confirmed"]
    assert d["deficiency"]["confirmed_by_id"] == t.uid["master"] and d["deficiency"]["confirmed_at"]
    # 재오픈 없음 — 버튼도 꺼져 있고 사유가 보인다
    assert not d["governance"]["can"]["reopen_request"] and "재오픈하지 않습니다" in d["governance"]["can"]["why"]["reopen"]
    assert _to(client, t, "master", did, "draft").status_code == 409
    acts = [e["action"] for e in client.get(f"{BASE}/{did}/governance-events", headers=t.h["staff"]).json()]
    assert acts == ["approve", "review_done", "submit_review"]


def test_self_approval_blocked(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})
    did = _new(client, t, "lead", final_conclusion="단순 미비점")
    assert _to(client, t, "lead", did, "review").status_code == 200
    assert _to(client, t, "lead", did, "confirmed", "x").status_code == 403       # 책임관리자 = 승인권 없음
    # 마스터 작성분은 외부 승인으로만
    did2 = _new(client, t, "master", final_conclusion="중요한 취약점")
    assert _to(client, t, "master", did2, "review").status_code == 200
    assert _to(client, t, "master", did2, "confirmed", "x").status_code == 409


def test_locked_while_review_and_after_confirm_but_status_moves(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})
    did = _new(client, t, "lead", final_conclusion="유의적 미비점")
    assert _to(client, t, "lead", did, "review").status_code == 200
    assert client.patch(f"{BASE}/{did}", headers=t.h["lead"], json={"severity": "high"}).status_code == 409
    assert client.patch(f"{BASE}/{did}", headers=t.h["lead"], json={"final_conclusion": None}).status_code == 409
    assert client.delete(f"{BASE}/{did}", headers=t.h["lead"]).status_code == 409
    assert _to(client, t, "master", did, "confirmed", "확정").status_code == 200
    assert client.patch(f"{BASE}/{did}", headers=t.h["lead"], json={"description": "x"}).status_code == 409
    r = client.patch(f"{BASE}/{did}", headers=t.h["lead"], json={"status": "in_progress"})   # 개선 진행은 계속
    assert r.status_code == 200 and r.json()["status"] == "in_progress"
    assert client.patch(f"{BASE}/{did}", headers=t.h["lead"], json={"severity": None}).status_code == 422


def test_withdraw_unlocks(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})
    did = _new(client, t, "lead", final_conclusion="단순 미비점")
    assert _to(client, t, "lead", did, "review").status_code == 200
    assert _to(client, t, "lead", did, "draft").status_code == 200
    r = client.patch(f"{BASE}/{did}", headers=t.h["lead"], json={"final_conclusion": None})
    assert r.status_code == 200 and r.json()["final_conclusion"] is None          # 이제 비울 수 있다


def test_external_approval_for_master_submission(client: TestClient, no_minio) -> None:
    t = T(client, {"master": ("icfr_manager",)})
    did = _new(client, t, "master", final_conclusion="중요한 취약점")
    assert _to(client, t, "master", did, "review").status_code == 200
    form = {"approver_body": "ceo", "approved_on": "2026-03-10"}
    assert client.post(f"{BASE}/{did}/external-approval", headers=t.h["master"], data={**form, "purpose": "reopen"},
                       files={"files": ("a.pdf", b"%PDF", "application/pdf")}).status_code == 409
    r = client.post(f"{BASE}/{did}/external-approval", headers=t.h["master"], data=form,
                    files={"files": ("a.pdf", b"%PDF", "application/pdf")})
    assert r.status_code == 200, r.text
    assert r.json()["deficiency"]["approval_status"] == "confirmed"
    assert next(iter(no_minio)).split("/")[2] == "deficiency"


def test_legacy_confirmed_is_kept(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})
    did = _new(client, t, "lead", final_conclusion="이전 결론")
    db = TestingSessionLocal()
    tok = set_active_tenant(t.tid)
    try:   # 2-3 이전 PATCH 로 확정이 적힌 건을 흉내낸다
        d = db.get(Deficiency, UUID(did))
        d.confirmed_at, d.confirmed_by_id = datetime.now(UTC), UUID(t.uid["master"])
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()
    r = client.get(f"{BASE}/{did}/approval", headers=t.h["lead"]).json()
    assert r["deficiency"]["approval_status"] == "confirmed" and r["legacy_confirmed"]
    assert r["governance"]["confirmed_by"]["name"] == "master"
    assert client.patch(f"{BASE}/{did}", headers=t.h["lead"], json={"severity": "low"}).status_code == 409


def test_inbox_and_permissions(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",), "admin": ("sys_admin",)})
    did = _new(client, t, "lead", final_conclusion="단순 미비점")
    assert _to(client, t, "admin", did, "review").status_code == 403              # 시스템관리자는 제도 업무 불가
    assert _to(client, t, "lead", did, "review").status_code == 200
    items = [i for i in client.get("/api/governance/inbox", headers=t.h["master"]).json()
             if i["entity_type"] == "deficiency"]
    assert [(i["entity_id"], i["action"]) for i in items] == [(did, "approve")]
    assert items[0]["path"] == f"/remediation?deficiency={did}"
