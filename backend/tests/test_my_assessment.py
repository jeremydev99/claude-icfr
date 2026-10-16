"""내 평가 — 테스트 작성·샘플·증빙·제출 (2026-10-15, ADR-0032 §2.10).

마스터 결정:
- 필요 샘플 수 = 설계평가 1 / 운영평가 RCM 표본수(없으면 자동통제 1, 그다음 수행 주기 기준표)
- **필요 수보다 적게는 제출할 수 없다** — 서버가 409 로 막는다
- 통제책임자는 본인 담당만, 전체 보기는 내부회계 관리자·감사(조회)만
"""
import io
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api import evidence as evidence_api
from app.core.security import hash_password
from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.models.assessment import AssessmentCycle, CycleTarget
from app.models.rcm_baseline import (
    BaselineControl,
    BaselineProcess,
    BaselineRisk,
    BaselineSubProcess,
)
from app.models.role_assignment import RoleAssignment
from app.models.tenant import UserTenantAccess
from app.models.user import User
from app.models.user_mgmt import UserRole
from app.services import sampling
from tests.conftest import TestingSessionLocal

PDF = b"%PDF-1.4 x"


@pytest.fixture
def storage(monkeypatch):
    store: dict[str, bytes] = {}
    monkeypatch.setattr(evidence_api, "upload_object", lambda k, d, c: store.__setitem__(k, d))
    monkeypatch.setattr(evidence_api, "get_object_stream", lambda k: io.BytesIO(store[k]))
    return store


def _login(client: TestClient, email: str, pw: str = "pw123456") -> dict:
    resp = client.post("/api/auth/login", data={"username": email, "password": pw})
    assert resp.status_code == 200, resp.text
    return {"Authorization": "Bearer " + resp.json()["access_token"]}


def _user(db, email: str, name: str, roles: tuple[str, ...] = ()) -> UUID:
    u = db.query(User).filter(User.email == email).first()
    if u is None:
        u = User(email=email, hashed_password=hash_password("pw123456"), display_name=name,
                 role="user", is_active=True)
        db.add(u)
        db.commit()
    if db.query(UserTenantAccess).filter(UserTenantAccess.user_id == u.id,
                                         UserTenantAccess.tenant_id == DEFAULT_TENANT_ID).first() is None:
        db.add(UserTenantAccess(user_id=u.id, tenant_id=DEFAULT_TENANT_ID, role="user"))
    for r in roles:
        if db.query(UserRole).filter(UserRole.user_id == u.id, UserRole.role_name == r).first() is None:
            db.add(UserRole(user_id=u.id, role_name=r))
    db.commit()
    return u.id


def _setup(suffix: str, *, sample_size: int | None = 2, kind: str = "operation") -> dict:
    """통제 1개(표본수 지정) + 회차 + 역할(책임자·평가자·관리자·제3자)."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        owner = _user(db, f"ma-owner-{suffix}@acme.example", f"책임자{suffix}")
        assessor = _user(db, f"ma-assessor-{suffix}@acme.example", f"평가자{suffix}")
        _user(db, f"ma-other-{suffix}@acme.example", f"제3자{suffix}")
        _user(db, f"ma-mgr-{suffix}@acme.example", f"관리자{suffix}", ("icfr_manager",))
        _user(db, f"ma-ext-{suffix}@acme.example", f"외부감사{suffix}", ("external_auditor",))
        p = BaselineProcess(code=f"MA{suffix}-P", name="P")
        db.add(p)
        db.flush()
        sp = BaselineSubProcess(code=f"MA{suffix}-SP", name="SP", process_id=p.id)
        db.add(sp)
        db.flush()
        r = BaselineRisk(code=f"MA{suffix}-R", description="R", assessment_level="LR", sub_process_id=sp.id)
        db.add(r)
        db.flush()
        c = BaselineControl(code=f"MA{suffix}-C", name="통제", risk_id=r.id, frequency="D",
                            sample_size=sample_size, population="매출 전표", test_methods="inquiry,inspection",
                            test_procedure="전표 승인 확인")
        db.add(c)
        db.flush()
        for role, uid in (("control_owner", owner), ("assessor", assessor)):
            db.add(RoleAssignment(scope="control", target_id=c.id, role_name=role, user_id=uid))
        cy = AssessmentCycle(kind=kind, frequency="annual", name=f"내평가-{suffix}",
                             period_start=date(2026, 1, 1), period_end=date(2026, 12, 31), status="open")
        db.add(cy)
        db.flush()
        db.add(CycleTarget(cycle_id=cy.id, control_id=c.id, control_code=c.code))
        db.commit()
        return {"control": str(c.id), "cycle": str(cy.id), "owner": f"ma-owner-{suffix}@acme.example",
                "assessor": f"ma-assessor-{suffix}@acme.example", "other": f"ma-other-{suffix}@acme.example",
                "mgr": f"ma-mgr-{suffix}@acme.example", "ext": f"ma-ext-{suffix}@acme.example"}
    finally:
        reset_active_tenant(tok)
        db.close()


def _start(client, s, h) -> dict:
    resp = client.post(f"/api/assessment/cycles/{s['cycle']}/activities", headers=h,
                       json={"control_id": s["control"], "activity_kind": "test"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _fill(client, s, h, sample: dict, n: int) -> None:
    assert client.patch(f"/api/assessment/samples/{sample['id']}", headers=h,
                        json={"label": f"전표-{n}", "result": "pass"}).status_code == 200
    up = client.post("/api/evidence/files", headers=h,
                     data={"cycle_id": s["cycle"], "control_id": s["control"], "sample_id": sample["id"]},
                     files={"file": (f"샘플{n}.pdf", PDF, "application/pdf")})
    assert up.status_code == 201, up.text


# ── 필요 샘플 수 규칙 ─────────────────────────────────────

def test_required_samples_rule() -> None:
    assert sampling.required_samples("design", {"sample_size": 7}) == 1
    assert sampling.required_samples("operation", {"sample_size": 7, "frequency": "D"}) == 7
    assert sampling.required_samples("operation", {"sample_size": None, "auto_manual": "A", "frequency": "D"}) == 1
    assert sampling.required_samples("operation", {"sample_size": None, "auto_manual": "M", "frequency": "D"}) == 20
    assert sampling.required_samples("operation", {"auto_manual": "IT", "frequency": "W"}) == 5   # IT의존 수동은 수동
    assert sampling.basis("operation", {"sample_size": 2}) == "RCM 표본수"


def test_rcm_excel_reads_sample_columns_by_header() -> None:
    """원천 엑셀 — 양식마다 열이 달라 헤더 이름으로 찾는다. A열 '샘플수'(감사인 협의, 93건 합계 197)가
    '표본수'(테스트방법 영역, 188)보다 우선이고, 다른 4건은 경고한다(2026-10-15 마스터 결정)."""
    from openpyxl import load_workbook

    from app.api.rcm import _parse_rcm_sheet
    from app.services.excel_parser import find_data_start_row, find_rcm_sheet

    path = Path(__file__).resolve().parents[1] / "seeds" / "2026_설계평가_RCM_리스트.xlsx"
    wb = load_workbook(path, data_only=True)
    name, hr, m = find_rcm_sheet(wb)
    ws = wb[name]
    parsed = _parse_rcm_sheet(ws, find_data_start_row(ws, hr, m["process_code"]) - 1, m)
    by = {c["code"]: c for c in parsed.controls}
    assert len(by) == 93 and sum(c["sample_size"] for c in by.values()) == 197
    assert by["SD-020-10-10"]["sample_size"] == 13 and by["SD-030-20-10"]["sample_size"] == 3
    assert len([w for w in parsed.warnings if "샘플수" in w]) == 4
    assert by["EL-010-10-10"]["test_methods"] == "inspection"
    assert by["EL-010-10-10"]["population"] and by["EL-010-10-10"]["test_procedure"]
    # 통제현황(AW열, 13.9-134) — 헤더 이름으로 93건 모두, 통제 설명(R열)과 다른 칸
    assert all(c.get("control_status") for c in by.values())
    assert by["EL-010-10-10"]["control_status"].startswith("1. 윤리헌장")
    assert by["EL-010-10-10"]["control_status"] != by["EL-010-10-10"]["description"]


# ── 작성 → 제출 ───────────────────────────────────────────

def test_draft_has_required_rows_and_rcm_prefill(client: TestClient) -> None:
    s = _setup("A1", sample_size=3)
    act = _start(client, s, _login(client, s["owner"]))
    assert act["status"] == "draft"
    assert [x["seq"] for x in act["samples"]] == [1, 2, 3]
    assert act["population"] == "매출 전표" and act["test_methods"] == "inquiry,inspection"
    # 같은 통제에 작성 중 기록은 하나
    again = client.post(f"/api/assessment/cycles/{s['cycle']}/activities", headers=_login(client, s["owner"]),
                        json={"control_id": s["control"], "activity_kind": "test"})
    assert again.status_code == 409


def test_cannot_submit_fewer_than_required(client: TestClient, storage) -> None:
    s = _setup("A2", sample_size=2)
    h = _login(client, s["owner"])
    act = _start(client, s, h)
    assert client.patch(f"/api/assessment/activities/{act['id']}", headers=h, json={"result": "pass"}).status_code == 200
    _fill(client, s, h, act["samples"][0], 1)
    r = client.post(f"/api/assessment/activities/{act['id']}/submit", headers=h)
    assert r.status_code == 409 and "2건 중 1건" in r.json()["detail"]
    # 줄을 지워 필요 수를 피할 수 없다
    assert client.delete(f"/api/assessment/samples/{act['samples'][1]['id']}", headers=h).status_code == 409
    # 결과만 있고 증빙이 없는 샘플도 미완
    client.patch(f"/api/assessment/samples/{act['samples'][1]['id']}", headers=h, json={"label": "전표-2", "result": "pass"})
    assert client.post(f"/api/assessment/activities/{act['id']}/submit", headers=h).status_code == 409


def test_submit_locks_and_approval_follows(client: TestClient, storage) -> None:
    s = _setup("A3", sample_size=2)
    h = _login(client, s["owner"])
    act = _start(client, s, h)
    # 제출 전 승인 불가
    ah = _login(client, s["assessor"])
    assert client.post(f"/api/assessment/activities/{act['id']}/approvals", headers=ah,
                       json={"stage": "assessor"}).status_code == 409
    for i, smp in enumerate(act["samples"], start=1):
        _fill(client, s, h, smp, i)
    # 더 보는 것은 허용 — 추가 줄은 채우거나 지워야 제출된다
    extra = client.post(f"/api/assessment/activities/{act['id']}/samples", headers=h, json={})
    assert extra.status_code == 201 and extra.json()["seq"] == 3
    assert client.post(f"/api/assessment/activities/{act['id']}/submit", headers=h).status_code == 409   # 결론 없음
    client.patch(f"/api/assessment/activities/{act['id']}", headers=h, json={"result": "pass"})
    assert client.post(f"/api/assessment/activities/{act['id']}/submit", headers=h).status_code == 409   # 3번 비어 있음
    assert client.delete(f"/api/assessment/samples/{extra.json()['id']}", headers=h).status_code == 204
    done = client.post(f"/api/assessment/activities/{act['id']}/submit", headers=h)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "submitted" and done.json()["required_samples"] == 2
    assert all(len(x["evidence"]) == 1 for x in done.json()["samples"])

    # 제출 후 잠금 — 기록·샘플·증빙 연결·증빙 삭제 모두
    assert client.patch(f"/api/assessment/activities/{act['id']}", headers=h, json={"note": "x"}).status_code == 409
    assert client.patch(f"/api/assessment/samples/{act['samples'][0]['id']}", headers=h,
                        json={"result": "fail"}).status_code == 409
    file_id = done.json()["samples"][0]["evidence"][0]["file_id"]
    assert client.delete(f"/api/evidence/files/{file_id}", headers=h).status_code == 409
    assert client.delete(f"/api/evidence/links/{done.json()['samples'][0]['evidence'][0]['link_id']}",
                         headers=h).status_code == 409

    assert client.post(f"/api/assessment/activities/{act['id']}/approvals", headers=ah,
                       json={"stage": "assessor"}).status_code == 201
    # 재수행 — 새 기록은 다시 작성 중
    again = _start(client, s, h)
    assert again["status"] == "draft" and again["id"] != act["id"]


def test_only_performer_edits_draft(client: TestClient, storage) -> None:
    s = _setup("A4", sample_size=1)
    act = _start(client, s, _login(client, s["owner"]))
    for who in ("other", "assessor", "mgr"):
        h = _login(client, s[who])
        assert client.patch(f"/api/assessment/activities/{act['id']}", headers=h,
                            json={"note": "x"}).status_code == 403, who
        assert client.post(f"/api/assessment/activities/{act['id']}/submit", headers=h).status_code == 403, who
    # 관리자는 증빙을 올릴 수 있어도 남의 작성 중 샘플에 연결하지 못한다
    up = client.post("/api/evidence/files", headers=_login(client, s["mgr"]),
                     data={"cycle_id": s["cycle"], "control_id": s["control"], "sample_id": act["samples"][0]["id"]},
                     files={"file": ("x.pdf", PDF, "application/pdf")})
    assert up.status_code == 403
    eh = _login(client, s["ext"])
    assert client.post(f"/api/assessment/activities/{act['id']}/submit", headers=eh).status_code == 403


def test_draft_is_incomplete_for_close(client: TestClient) -> None:
    s = _setup("A5", sample_size=1)
    _start(client, s, _login(client, s["owner"]))
    inc = client.get(f"/api/assessment/cycles/{s['cycle']}/incomplete", headers=_login(client, s["mgr"])).json()
    assert any(i["control_id"] == s["control"] for i in inc["items"])


def test_design_cycle_needs_one_sample(client: TestClient) -> None:
    s = _setup("A6", sample_size=7, kind="design")
    act = client.post(f"/api/assessment/cycles/{s['cycle']}/activities", headers=_login(client, s["owner"]),
                      json={"control_id": s["control"], "activity_kind": "design"})
    assert act.status_code == 201, act.text
    assert len(act.json()["samples"]) == 1


# ── 내 평가 목록 ──────────────────────────────────────────

def test_worklist_mine_and_full_view(client: TestClient, storage) -> None:
    s = _setup("A7", sample_size=2)
    oh = _login(client, s["owner"])
    rows = client.get(f"/api/assessment/cycles/{s['cycle']}/worklist", headers=oh).json()
    row = next(r for r in rows if r["control_id"] == s["control"])
    assert row["state"] == "not_started" and row["required_samples"] == 2
    assert row["sample_basis"] == "RCM 표본수" and row["my_roles"] == ["control_owner"]
    assert row["rcm_population"] == "매출 전표"

    act = _start(client, s, oh)
    _fill(client, s, oh, act["samples"][0], 1)
    row = next(r for r in client.get(f"/api/assessment/cycles/{s['cycle']}/worklist", headers=oh).json()
               if r["control_id"] == s["control"])
    assert row["state"] == "draft" and row["samples_done"] == 1 and row["evidence_count"] == 1

    # 제3자 — 내 담당 없음, 전체 보기 403
    xh = _login(client, s["other"])
    assert all(r["control_id"] != s["control"]
               for r in client.get(f"/api/assessment/cycles/{s['cycle']}/worklist", headers=xh).json())
    assert client.get(f"/api/assessment/cycles/{s['cycle']}/worklist", headers=xh,
                      params={"mine": "false"}).status_code == 403
    assert client.get(f"/api/assessment/cycles/{s['cycle']}/worklist", headers=oh,
                      params={"mine": "false"}).status_code == 403
    # 관리자·외부감사인은 전체 조회
    for who in ("mgr", "ext"):
        full = client.get(f"/api/assessment/cycles/{s['cycle']}/worklist", headers=_login(client, s[who]),
                          params={"mine": "false"})
        assert full.status_code == 200 and any(r["control_id"] == s["control"] for r in full.json())
    # 평가자 — 승인 대기 목록으로 본다
    arow = next(r for r in client.get(f"/api/assessment/cycles/{s['cycle']}/worklist",
                                      headers=_login(client, s["assessor"])).json() if r["control_id"] == s["control"])
    assert arow["my_roles"] == ["assessor"] and arow["can_approve"] == []


# ── 직무분리 — 승인 시점 판정 (2026-10-16, 조사 1) ─────────────

def _submitted(client, s) -> dict:
    h = _login(client, s["owner"])
    act = _start(client, s, h)
    for i, smp in enumerate(act["samples"], start=1):
        _fill(client, s, h, smp, i)
    client.patch(f"/api/assessment/activities/{act['id']}", headers=h, json={"result": "pass"})
    assert client.post(f"/api/assessment/activities/{act['id']}/submit", headers=h).status_code == 200
    return act


def _reassign(s, role: str, email: str) -> None:
    """이 통제의 역할 보유자를 바꾼다(없으면 만든다)."""
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        uid = db.query(User).filter(User.email == email).first().id
        ra = db.query(RoleAssignment).filter(RoleAssignment.target_id == UUID(s["control"]),
                                             RoleAssignment.role_name == role).first()
        if ra is None:
            db.add(RoleAssignment(scope="control", target_id=UUID(s["control"]), role_name=role, user_id=uid))
        else:
            ra.user_id = uid
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()


def test_performer_cannot_approve_own_test_even_after_reassignment(client: TestClient, storage) -> None:
    """제출 뒤 작성자가 평가자로 배정돼도 자기 기록은 승인하지 못한다 — 목록에도 승인 버튼 대신 사유."""
    s = _setup("S1", sample_size=1)
    act = _submitted(client, s)
    _reassign(s, "assessor", s["owner"])
    h = _login(client, s["owner"])
    r = client.post(f"/api/assessment/activities/{act['id']}/approvals", headers=h, json={"stage": "assessor"})
    assert r.status_code == 403 and "본인이 작성한" in r.json()["detail"]
    row = next(x for x in client.get(f"/api/assessment/cycles/{s['cycle']}/worklist", headers=h).json()
               if x["control_id"] == s["control"])
    assert row["can_approve"] == [] and "본인이 작성한" in row["sod_blocked"]
    # 다른 사람에게 돌려주면 승인된다
    _reassign(s, "assessor", s["assessor"])
    ah = _login(client, s["assessor"])
    row = next(x for x in client.get(f"/api/assessment/cycles/{s['cycle']}/worklist", headers=ah).json()
               if x["control_id"] == s["control"])
    assert row["can_approve"] == ["assessor"] and row["sod_blocked"] is None
    assert client.post(f"/api/assessment/activities/{act['id']}/approvals", headers=ah,
                       json={"stage": "assessor"}).status_code == 201


def test_same_person_cannot_approve_two_stages(client: TestClient, storage) -> None:
    """부서승인자 = 평가자인 사람은 한 단계만 승인한다."""
    s = _setup("S2", sample_size=1)
    _reassign(s, "dept_approver", s["assessor"])
    act = _submitted(client, s)
    ah = _login(client, s["assessor"])
    assert client.post(f"/api/assessment/activities/{act['id']}/approvals", headers=ah,
                       json={"stage": "dept"}).status_code == 201
    r = client.post(f"/api/assessment/activities/{act['id']}/approvals", headers=ah, json={"stage": "assessor"})
    assert r.status_code == 403 and "다른 단계" in r.json()["detail"]


# ── 점검 보완 (2026-10-16 브라우저 점검) ─────────────────────

def test_same_sample_same_file_is_refused(client: TestClient, storage) -> None:
    """같은 샘플에 같은 내용은 409 — 다른 샘플에는 올리되 duplicate_of 로 알린다."""
    s = _setup("P1", sample_size=2)
    h = _login(client, s["owner"])
    act = _start(client, s, h)
    s1, s2 = act["samples"][0]["id"], act["samples"][1]["id"]

    def up(sid):
        return client.post("/api/evidence/files", headers=h,
                           data={"cycle_id": s["cycle"], "control_id": s["control"], "sample_id": sid},
                           files={"file": ("캡처.pdf", PDF, "application/pdf")})
    assert up(s1).status_code == 201
    again = up(s1)
    assert again.status_code == 409 and "이미 붙어 있습니다" in again.json()["detail"]
    other = up(s2)
    assert other.status_code == 201 and other.json()["duplicate_of"] == "캡처.pdf"


def test_worklist_flags_missing_dept_approver(client: TestClient) -> None:
    """부서승인이 켜져 있는데 부서승인자가 없으면 표시 — 그대로면 승인 대기에서 끝나지 않는다."""
    s = _setup("P2", sample_size=1)
    row = next(x for x in client.get(f"/api/assessment/cycles/{s['cycle']}/worklist",
                                      headers=_login(client, s["owner"])).json() if x["control_id"] == s["control"])
    assert row["dept_approver_missing"] is True
    _reassign(s, "dept_approver", s["other"])
    row = next(x for x in client.get(f"/api/assessment/cycles/{s['cycle']}/worklist",
                                      headers=_login(client, s["owner"])).json() if x["control_id"] == s["control"])
    assert row["dept_approver_missing"] is False
