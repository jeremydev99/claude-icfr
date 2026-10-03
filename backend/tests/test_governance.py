"""검토·승인 거버넌스 (ADR-0038) — §4 검증 조건.

테스트마다 **새 테넌트**를 만든다. 승인 경로가 "책임관리자가 있는가"에 달려 있어 기본 테넌트를 공유하면
다른 테스트가 만든 책임관리자에 결과가 흔들린다.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import scoping as scoping_api
from app.core.security import hash_password
from app.core.tenant_context import reset_active_tenant, set_active_tenant
from app.models.tenant import Tenant, UserTenantAccess
from app.models.user import User
from app.models.user_mgmt import UserRole
from app.services.approval import path_for
from seeds.seed_scoping_template import load_template
from tests.conftest import TestingSessionLocal

PW = "pw123456"


@pytest.fixture(scope="module", autouse=True)
def template(app):
    db = TestingSessionLocal()
    try:
        tpl, _, created = load_template(db)
        if created:
            db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def no_minio(monkeypatch):
    stored = {}
    monkeypatch.setattr(scoping_api, "upload_object", lambda key, data, mime: stored.__setitem__(key, data))
    return stored


class T:
    """새 테넌트 + 역할별 사용자. h[name] = 로그인 헤더."""

    def __init__(self, client: TestClient, people: dict[str, tuple[str, ...]]):
        self.tid = uuid4()
        self.h: dict[str, dict] = {}
        self.uid: dict[str, str] = {}
        db = TestingSessionLocal()
        try:
            db.add(Tenant(id=self.tid, name=f"거버넌스{self.tid.hex[:4]}", code=f"GOV-{self.tid.hex[:6]}", is_active=True))
            db.commit()
            for name, roles in people.items():
                email = f"{name}-{self.tid.hex[:6]}@acme.example"
                u = User(email=email, hashed_password=hash_password(PW), display_name=name, role="user", is_active=True)
                db.add(u)
                db.commit()
                db.add(UserTenantAccess(user_id=u.id, tenant_id=self.tid, role="user"))
                db.commit()
                tok = set_active_tenant(self.tid)
                try:
                    for r in roles:
                        db.add(UserRole(user_id=u.id, role_name=r))
                    db.commit()
                finally:
                    reset_active_tenant(tok)
                self.uid[name] = str(u.id)
                r = client.post("/api/auth/login", data={"username": email, "password": PW})
                assert r.status_code == 200, r.text
                self.h[name] = {"Authorization": "Bearer " + r.json()["access_token"], "X-Tenant-Id": str(self.tid)}
        finally:
            db.close()


def _new(client, t: T, who: str, year: int = 2030) -> tuple[str, dict]:
    r = client.post("/api/scoping", headers=t.h[who], json={"fiscal_year": year})
    assert r.status_code == 201, r.text
    return f"/api/scoping/{r.json()['id']}", r.json()


def _tr(client, base, h, to, reason=None):
    return client.post(f"{base}/transition", headers=h, json={"to_status": to, "reason": reason})


def test_path_for_rules() -> None:
    assert path_for(1, True) == "lead_then_master"
    assert path_for(1, False) == "master"
    assert path_for(2, True) == "master"
    assert path_for(3, True) == "external"


def test_staff_lead_master_path_and_no_self_approval(client: TestClient) -> None:
    t = T(client, {"staff": ("icfr_staff",), "staff2": ("icfr_staff",), "lead": ("icfr_lead",),
                   "master": ("icfr_manager",)})
    base, _ = _new(client, t, "staff")
    d = _tr(client, base, t.h["staff"], "review").json()
    g = d["governance"]
    assert g["review_path"] == "lead_then_master" and g["requested_by"]["name"] == "staff"
    # 검토 중에는 수정 불가
    assert client.patch(base, headers=t.h["staff"], json={"rationale": "x"}).status_code == 409
    # 검토 전 승인 불가, 다른 일반관리자 검토 불가
    assert _tr(client, base, t.h["master"], "confirmed", "확정").status_code == 409
    assert client.post(f"{base}/review", headers=t.h["staff2"], json={"action": "done"}).status_code == 409
    d = client.post(f"{base}/review", headers=t.h["lead"], json={"action": "done"}).json()
    assert d["governance"]["reviewed_by"]["name"] == "lead"
    # 검토자는 승인 불가(마스터 아님), 마스터 승인 → 확정
    assert _tr(client, base, t.h["lead"], "confirmed", "확정").status_code == 403
    d = _tr(client, base, t.h["master"], "confirmed", "확정").json()
    assert d["status"] == "confirmed" and d["governance"]["confirmed_by"]["name"] == "master"


def test_requester_cannot_approve_own(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",), "master2": ("icfr_manager",)})
    base, _ = _new(client, t, "lead")
    assert _tr(client, base, t.h["lead"], "review").json()["governance"]["review_path"] == "master"
    d = _tr(client, base, t.h["master"], "confirmed", "확정")
    assert d.status_code == 200
    # 마스터가 요청한 건 → 외부 승인 경로, 내부 승인(다른 마스터 포함) 불가
    base2, _ = _new(client, t, "master", 2031)
    assert _tr(client, base2, t.h["master"], "review").json()["governance"]["review_path"] == "external"
    assert _tr(client, base2, t.h["master"], "confirmed", "확정").status_code == 409
    assert _tr(client, base2, t.h["master2"], "confirmed", "확정").status_code == 409


def test_no_lead_means_staff_goes_to_master(client: TestClient) -> None:
    t = T(client, {"staff": ("icfr_staff",), "master": ("icfr_manager",)})
    base, _ = _new(client, t, "staff")
    assert _tr(client, base, t.h["staff"], "review").json()["governance"]["review_path"] == "master"
    assert _tr(client, base, t.h["master"], "confirmed", "확정").status_code == 200


def test_external_approval_requires_evidence(client: TestClient, no_minio) -> None:
    t = T(client, {"master": ("icfr_manager",), "lead": ("icfr_lead",)})
    base, _ = _new(client, t, "master")
    _tr(client, base, t.h["master"], "review")
    form = {"purpose": "approve", "approver_body": "board", "approved_on": "2030-03-20", "reference": "제5차 이사회"}
    r = client.post(f"{base}/external-approval", headers=t.h["master"], data=form,
                    files=[("files", ("", b"", "application/pdf"))])
    assert r.status_code in (422, 400)
    r = client.post(f"{base}/external-approval", headers=t.h["lead"], data=form,
                    files=[("files", ("의사록.pdf", b"%PDF-1.4 x", "application/pdf"))])
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "confirmed"
    ext = d["governance"]["external_approvals"][0]
    assert ext["approver_body"] == "board" and ext["files"][0]["filename"] == "의사록.pdf"
    assert len(no_minio) == 1 and "/governance/scoping/" in next(iter(no_minio))
    ev = client.get(f"{base}/events", headers=t.h["lead"]).json()
    assert ev[0]["action"] == "external_approve" and "이사회" in ev[0]["reason"]


def test_reopen_needs_other_master_and_bumps_version(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})
    base, _ = _new(client, t, "lead")
    _tr(client, base, t.h["lead"], "review")
    _tr(client, base, t.h["master"], "confirmed", "확정")
    assert _tr(client, base, t.h["master"], "draft", "x").status_code == 409
    d = client.post(f"{base}/reopen-requests", headers=t.h["lead"], json={"reason": "금액 수정"}).json()
    rid = d["governance"]["pending_reopen"]["id"]
    assert client.post(f"{base}/reopen-requests", headers=t.h["lead"], json={"reason": "또"}).status_code == 409
    assert d["status"] == "confirmed"   # 요청만으로는 안 바뀐다
    assert client.post(f"{base}/reopen-requests/{rid}/decide", headers=t.h["lead"],
                       json={"approve": True}).status_code == 403
    assert client.post(f"{base}/reopen-requests/{rid}/decide", headers=t.h["master"],
                       json={"approve": False}).status_code == 422   # 거절 사유 필수
    d = client.post(f"{base}/reopen-requests/{rid}/decide", headers=t.h["master"], json={"approve": True}).json()
    assert d["status"] == "draft" and d["governance"]["version"] == 2


def test_master_reopen_request_needs_external(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",), "master2": ("icfr_manager",)})
    base, _ = _new(client, t, "lead")
    _tr(client, base, t.h["lead"], "review")
    _tr(client, base, t.h["master"], "confirmed", "확정")
    d = client.post(f"{base}/reopen-requests", headers=t.h["master"], json={"reason": "재검토"}).json()
    rid = d["governance"]["pending_reopen"]["id"]
    assert d["governance"]["can"]["reopen_external"] is True
    assert client.post(f"{base}/reopen-requests/{rid}/decide", headers=t.h["master2"],
                       json={"approve": True}).status_code == 409
    r = client.post(f"{base}/external-approval", headers=t.h["lead"],
                    data={"purpose": "reopen", "approver_body": "ceo", "approved_on": "2030-05-01"},
                    files=[("files", ("결재.png", b"\x89PNG", "image/png"))])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "draft"


def test_item_confirm_history_keeps_confirmer(client: TestClient) -> None:
    t = T(client, {"staff": ("icfr_staff",), "staff2": ("icfr_staff",)})
    base, s = _new(client, t, "staff")
    acc = next(a for a in s["accounts"] if a["badges"])
    client.post(f"{base}/confirm", headers=t.h["staff"], json={"scope": "account", "target_id": acc["id"]})
    client.post(f"{base}/confirm", headers=t.h["staff2"], json={"scope": "account", "target_id": acc["id"], "undo": True})
    client.post(f"{base}/confirm", headers=t.h["staff2"], json={"scope": "account", "target_id": acc["id"]})
    ev = [e for e in client.get(f"{base}/events", headers=t.h["staff"]).json() if e["action"].startswith("item_")]
    acts = []
    for e in reversed(ev):   # 계정 한 줄 확인은 필드 수만큼 이벤트가 생긴다 — 연속 중복을 하나로
        a = (e["action"], e["actor"]["name"])
        if not acts or acts[-1] != a:
            acts.append(a)
    assert acts[0] == ("item_confirm", "staff")
    assert acts == [("item_confirm", "staff"), ("item_unconfirm", "staff2"), ("item_confirm", "staff2")]
    unconf = next(e for e in ev if e["action"] == "item_unconfirm")
    assert unconf["before"]["확인자"] == t.uid["staff"]   # 지워진 확인자가 이력에 남는다


def test_value_change_records_before_after(client: TestClient) -> None:
    t = T(client, {"staff": ("icfr_staff",)})
    base, s = _new(client, t, "staff")
    acc = s["accounts"][0]
    client.patch(f"{base}/accounts/{acc['id']}", headers=t.h["staff"], json={"qual_basis": "새 근거"})
    ev = client.get(f"{base}/events", headers=t.h["staff"]).json()
    vc = next(e for e in ev if e["action"] == "value_change" and "계정" in (e["target"] or ""))
    assert vc["after"]["질적 판단 근거"] == "새 근거" and vc["actor"]["name"] == "staff"


def test_sys_admin_only_cannot_work_and_tier_is_exclusive(client: TestClient) -> None:
    t = T(client, {"admin": ("sys_admin",), "master": ("icfr_manager", "sys_admin"), "x": ()})
    assert client.post("/api/scoping", headers=t.h["admin"], json={"fiscal_year": 2040}).status_code == 403
    # 마스터+시스템관리자 겸직은 허용 — 작업 가능
    assert client.post("/api/scoping", headers=t.h["master"], json={"fiscal_year": 2040}).status_code == 201
    # 1~3단계 중복 배정 409, 4단계 겸직 허용
    h = t.h["master"]
    assert client.post("/api/users/roles", headers=h, json={"user_id": t.uid["x"], "role_name": "icfr_staff"}).status_code == 201
    assert client.post("/api/users/roles", headers=h, json={"user_id": t.uid["x"], "role_name": "icfr_lead"}).status_code == 409
    assert client.post("/api/users/roles", headers=h, json={"user_id": t.uid["x"], "role_name": "sys_admin"}).status_code == 201


def test_inbox_lists_my_pending_actions(client: TestClient) -> None:
    t = T(client, {"staff": ("icfr_staff",), "lead": ("icfr_lead",), "master": ("icfr_manager",)})
    base, _ = _new(client, t, "staff")
    _tr(client, base, t.h["staff"], "review")
    assert [i["action"] for i in client.get("/api/governance/inbox", headers=t.h["lead"]).json()] == ["review"]
    assert client.get("/api/governance/inbox", headers=t.h["master"]).json() == []
    assert client.get("/api/governance/inbox", headers=t.h["staff"]).json() == []
    client.post(f"{base}/review", headers=t.h["lead"], json={"action": "done"})
    assert [i["action"] for i in client.get("/api/governance/inbox", headers=t.h["master"]).json()] == ["approve"]
