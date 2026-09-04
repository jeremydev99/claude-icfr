"""평가 회차·활동·승인 검증 (3-2, ADR-0032).

**핵심은 두 가지다.**
- `test_cycle_targets_only_matching_frequency` (§5-3) — 주기 기반 자동 대상 선정.
  이게 없으면 전 통제를 대상으로 묶는 구현도 나머지를 통과한다.
- `test_close_with_incomplete_requires_reason` (§5-7) — 막지 않고 기록하는지(§2.5).

sqlite 는 FK 를 강제하지 않으므로 복합 FK 교차 테넌트 거부는 여기서 검증할 수 없다
(ADR-0030 때와 같음). ORM 자동 격리 레벨만 본다.
"""
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.models.assessment import AssessmentCycle
from app.models.org import Department, UserDepartment
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
from tests.conftest import TestingSessionLocal


def _headers(client: TestClient, email="admin@acme.example", pw="admin123") -> dict:
    resp = client.post("/api/auth/login", data={"username": email, "password": pw})
    assert resp.status_code == 200, resp.text
    return {"Authorization": "Bearer " + resp.json()["access_token"]}


def _user(db, email: str, name: str) -> UUID:
    u = db.query(User).filter(User.email == email).first()
    if u is None:
        u = User(email=email, hashed_password=hash_password("pw123456"),
                 display_name=name, role="user", is_active=True)
        db.add(u)
        db.commit()
    if db.query(UserTenantAccess).filter(
        UserTenantAccess.user_id == u.id,
        UserTenantAccess.tenant_id == DEFAULT_TENANT_ID,
    ).first() is None:
        db.add(UserTenantAccess(user_id=u.id, tenant_id=DEFAULT_TENANT_ID, role="user"))
        db.commit()
    return u.id


def _control(db, suffix: str, freq: str = "annual") -> tuple[UUID, UUID]:
    """baseline 4단 체인 → (process_id, control_id). 활성 tenant 안에서 호출."""
    p = BaselineProcess(code=f"AC{suffix}-P", name="P")
    db.add(p)
    db.flush()
    sp = BaselineSubProcess(code=f"AC{suffix}-SP", name="SP", process_id=p.id)
    db.add(sp)
    db.flush()
    r = BaselineRisk(code=f"AC{suffix}-R", description="R", assessment_level="LR",
                     sub_process_id=sp.id)
    db.add(r)
    db.flush()
    c = BaselineControl(code=f"AC{suffix}-C", name="C", risk_id=r.id,
                        assessment_frequency=freq)
    db.add(c)
    db.commit()
    return p.id, c.id


def _assign(db, control_id: UUID, role: str, user_id: UUID) -> None:
    db.add(RoleAssignment(scope="control", target_id=control_id,
                          role_name=role, user_id=user_id))
    db.commit()


def _grant_icfr_manager(db) -> None:
    """정책 변경은 icfr_manager 전용이다(ADR-0031 §2.6). 정책을 건드리는 테스트가
    먼저 권한을 확보한다 — 다른 테스트의 부수효과에 기대지 않는다."""
    admin = db.query(User).filter(User.email == "admin@acme.example").one()
    if db.query(UserRole).filter(UserRole.user_id == admin.id,
                                 UserRole.role_name == "icfr_manager").first() is None:
        db.add(UserRole(user_id=admin.id, role_name="icfr_manager"))
        db.commit()


def _ctx():
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    return db, tok


# ── §5-1 평가주기 baseline + override ─────────────────────

def test_assessment_frequency_from_baseline_and_override(client: TestClient) -> None:
    """§5-1 — 주기가 baseline 기본값에서 나오고 overlay override 가 우선한다."""
    h = _headers(client)
    db, tok = _ctx()
    try:
        _, ctrl = _control(db, "F1", freq="quarterly")
    finally:
        reset_active_tenant(tok)
        db.close()

    body = client.get(f"/api/rcm/controls/{ctrl}", headers=h).json()
    assert body["assessment_frequency"] == "quarterly"

    resp = client.patch(f"/api/rcm/controls/{ctrl}",
                        json={"assessment_frequency": "monthly"}, headers=h)
    assert resp.status_code == 200, resp.text
    assert resp.json()["assessment_frequency"] == "monthly"      # override 우선
    assert resp.json()["is_overridden"] is True


# ── §5-4 기간 제안 (지시 §5-4 재서술 — 시작월 해석) ────────

def test_period_suggestion_default_fiscal_year(client: TestClient) -> None:
    """§5-4(재서술) — **기본값 1일 때 1분기가 1/1~3/31.** 12월 결산 회사 회귀 가드.

    한국 상장사 대부분이 12월 결산이며 회계연도가 1/1~12/31 이다.
    """
    h = _headers(client)
    body = client.get("/api/assessment/period-suggestion", headers=h,
                      params={"frequency": "quarterly", "fiscal_year": 2026,
                              "period_index": 1}).json()
    assert body["fiscal_year_start_month"] == 1
    assert body["period_start"] == "2026-01-01"
    assert body["period_end"] == "2026-03-31"


def test_period_suggestion_march_closing_company(client: TestClient) -> None:
    """§5-4(재서술) — **회계연도 시작월이 4일 때 1분기가 4/1~6/30.**

    3월 결산 회사의 회계연도는 4/1~3/31 이므로 시작월은 4다.
    지시서 §5-4 는 "시작월 3"으로 적었으나 그것은 결산월이며 오류다(마스터 확인).
    """
    h = _headers(client)
    db, tok = _ctx()
    try:
        _grant_icfr_manager(db)
    finally:
        reset_active_tenant(tok)
        db.close()
    resp = client.put("/api/org/policies", headers=h, json={
        "policy_key": "fiscal_year_start_month", "policy_value": "4"})
    assert resp.status_code == 200, resp.text
    try:
        body = client.get("/api/assessment/period-suggestion", headers=h,
                          params={"frequency": "quarterly", "fiscal_year": 2026,
                                  "period_index": 1}).json()
        assert body["fiscal_year_start_month"] == 4
        assert body["period_start"] == "2026-04-01"
        assert body["period_end"] == "2026-06-30"
    finally:
        # 정책은 테넌트 전역 상태다 — 남기면 이후 테스트가 전부 영향받는다
        client.put("/api/org/policies", headers=h, json={
            "policy_key": "fiscal_year_start_month", "policy_value": "1"})


# ── §5-3 핵심: 주기 기반 자동 대상 선정 ───────────────────

def test_cycle_targets_only_matching_frequency(client: TestClient) -> None:
    """§5-3 **핵심** — 분기 회차는 분기 주기 통제만 대상. 주/월 주기는 미포함.

    이게 없으면 전 통제를 대상으로 묶는 구현도 나머지를 전부 통과한다.
    """
    h = _headers(client)
    db, tok = _ctx()
    try:
        assessor = _user(db, "assessor-t@acme.example", "평가자")
        _, q_ctrl = _control(db, "T1", freq="quarterly")
        _, m_ctrl = _control(db, "T2", freq="monthly")
        _, w_ctrl = _control(db, "T3", freq="weekly")
        _assign(db, q_ctrl, "assessor", assessor)
    finally:
        reset_active_tenant(tok)
        db.close()

    ah = _headers(client, "assessor-t@acme.example", "pw123456")
    cycle = client.post("/api/assessment/cycles", headers=ah, json={
        "kind": "operation", "frequency": "quarterly", "name": "2026년 1분기 운영평가-T",
        "fiscal_year": 2026, "period_index": 1}).json()

    targets = client.get(f"/api/assessment/cycles/{cycle['id']}/targets",
                         headers=h, params={"limit": 500}).json()["items"]
    ids = {t["control_id"] for t in targets}
    assert str(q_ctrl) in ids
    assert str(m_ctrl) not in ids
    assert str(w_ctrl) not in ids


# ── §5-2 두 종류 독립 ─────────────────────────────────────

def test_design_and_operation_cycles_are_independent(client: TestClient) -> None:
    """§5-2 — 설계평가·운영평가 회차를 동시에 열 수 있고 서로 영향 없다."""
    db, tok = _ctx()
    try:
        assessor = _user(db, "assessor-i@acme.example", "평가자I")
        _, ctrl = _control(db, "I1", freq="annual")
        _assign(db, ctrl, "assessor", assessor)
    finally:
        reset_active_tenant(tok)
        db.close()

    ah = _headers(client, "assessor-i@acme.example", "pw123456")
    for kind in ("design", "operation"):
        resp = client.post("/api/assessment/cycles", headers=ah, json={
            "kind": kind, "frequency": "annual", "name": f"2026년 {kind}-I",
            "fiscal_year": 2026, "period_index": 1})
        assert resp.status_code == 201, resp.text

    body = client.get("/api/assessment/cycles", headers=ah, params={"limit": 500}).json()
    names = {c["name"] for c in body["items"]}
    assert {"2026년 design-I", "2026년 operation-I"} <= names


# ── §5-5 생성 권한 ────────────────────────────────────────

def test_control_owner_cannot_create_cycle(client: TestClient) -> None:
    """§5-5 — `control_owner` 는 회차를 만들 수 없다. 평가 일정은 전담부서가 정한다."""
    db, tok = _ctx()
    try:
        owner = _user(db, "owner-c@acme.example", "통제책임자C")
        _, ctrl = _control(db, "C1", freq="annual")
        _assign(db, ctrl, "control_owner", owner)
    finally:
        reset_active_tenant(tok)
        db.close()

    oh = _headers(client, "owner-c@acme.example", "pw123456")
    resp = client.post("/api/assessment/cycles", headers=oh, json={
        "kind": "operation", "frequency": "annual", "name": "권한없는회차",
        "fiscal_year": 2026, "period_index": 1})
    assert resp.status_code == 403, resp.text
    assert "평가자" in resp.json()["detail"]


# ── §5-6 통제 단위 권한 ───────────────────────────────────

def test_activity_permission_is_per_control(client: TestClient) -> None:
    """§5-6 — 통제 A 의 평가자가 통제 B 에서 평가를 남길 수 없다.

    "이 사람이 평가자인가"가 아니라 "이 통제에서 평가자인가"를 본다(ADR-0031 §2.2).
    """
    db, tok = _ctx()
    try:
        a_assessor = _user(db, "assessor-a@acme.example", "A평가자")
        b_assessor = _user(db, "assessor-b@acme.example", "B평가자")
        _, ctrl_a = _control(db, "P1", freq="annual")
        _, ctrl_b = _control(db, "P2", freq="annual")
        _assign(db, ctrl_a, "assessor", a_assessor)
        _assign(db, ctrl_b, "assessor", b_assessor)
    finally:
        reset_active_tenant(tok)
        db.close()

    ah = _headers(client, "assessor-a@acme.example", "pw123456")
    cycle = client.post("/api/assessment/cycles", headers=ah, json={
        "kind": "operation", "frequency": "annual", "name": "2026 통제단위권한",
        "fiscal_year": 2026, "period_index": 1}).json()

    ok = client.post(f"/api/assessment/cycles/{cycle['id']}/activities", headers=ah, json={
        "control_id": str(ctrl_a), "activity_kind": "operation_assessment", "result": "적정"})
    assert ok.status_code == 201, ok.text

    denied = client.post(f"/api/assessment/cycles/{cycle['id']}/activities", headers=ah, json={
        "control_id": str(ctrl_b), "activity_kind": "operation_assessment"})
    assert denied.status_code == 403, denied.text


# ── §5-11 활동 기록 감사추적 ──────────────────────────────

def test_activity_records_performer_and_time(client: TestClient) -> None:
    """§5-11 — 수행자·수행시각이 남고 조회된다(ADR-0032 §2.8 감사추적)."""
    db, tok = _ctx()
    try:
        assessor = _user(db, "assessor-r@acme.example", "기록평가자")
        _, ctrl = _control(db, "R1", freq="annual")
        _assign(db, ctrl, "assessor", assessor)
    finally:
        reset_active_tenant(tok)
        db.close()

    ah = _headers(client, "assessor-r@acme.example", "pw123456")
    cycle = client.post("/api/assessment/cycles", headers=ah, json={
        "kind": "operation", "frequency": "annual", "name": "2026 기록검증",
        "fiscal_year": 2026, "period_index": 1}).json()
    client.post(f"/api/assessment/cycles/{cycle['id']}/activities", headers=ah, json={
        "control_id": str(ctrl), "activity_kind": "operation_assessment", "result": "적정"})

    items = client.get(f"/api/assessment/cycles/{cycle['id']}/activities",
                       headers=ah).json()["items"]
    rec = next(a for a in items if a["control_id"] == str(ctrl))
    assert rec["performed_by_id"] == str(assessor)
    assert rec["performed_by_name"] == "기록평가자"
    assert rec["performed_at"]


# ── §5-7 핵심: 마감 ───────────────────────────────────────

def test_close_with_incomplete_requires_reason(client: TestClient) -> None:
    """§5-7 **핵심** — 미완이 있으면 사유 없이는 거부, 사유가 있으면 마감 + 목록 보존.

    막으면 회차가 영원히 안 닫히고, 조용히 허용하면 무엇이 빠졌는지 남지 않는다.
    """
    db, tok = _ctx()
    try:
        assessor = _user(db, "assessor-x@acme.example", "마감평가자")
        _, ctrl = _control(db, "X1", freq="annual")
        _assign(db, ctrl, "assessor", assessor)
    finally:
        reset_active_tenant(tok)
        db.close()

    ah = _headers(client, "assessor-x@acme.example", "pw123456")
    cycle = client.post("/api/assessment/cycles", headers=ah, json={
        "kind": "operation", "frequency": "annual", "name": "2026 마감검증",
        "fiscal_year": 2026, "period_index": 1}).json()

    # 미완 목록을 마감 전에 미리 볼 수 있다
    pre = client.get(f"/api/assessment/cycles/{cycle['id']}/incomplete", headers=ah).json()
    assert pre["total"] >= 1
    assert "test" in next(i for i in pre["items"] if i["control_id"] == str(ctrl))["missing"]

    without = client.post(f"/api/assessment/cycles/{cycle['id']}/close", headers=ah, json={})
    assert without.status_code == 409, without.text
    assert "사유" in without.json()["detail"]

    with_reason = client.post(f"/api/assessment/cycles/{cycle['id']}/close", headers=ah,
                              json={"incomplete_reason": "담당자 휴직으로 차기 회차 이월"})
    assert with_reason.status_code == 200, with_reason.text
    body = with_reason.json()
    assert body["cycle"]["status"] == "closed"
    assert body["cycle"]["incomplete_reason"] == "담당자 휴직으로 차기 회차 이월"
    assert len(body["incomplete"]) >= 1          # 미완 내역이 응답에 보존된다

    # 마감된 회차에는 더 기록할 수 없다
    after = client.post(f"/api/assessment/cycles/{cycle['id']}/activities", headers=ah, json={
        "control_id": str(ctrl), "activity_kind": "operation_assessment"})
    assert after.status_code == 409


# ── §5-10 최종승인 ────────────────────────────────────────

def test_final_approval_requires_closed_cycle(client: TestClient) -> None:
    """§5-10 — 마감되지 않은 회차는 최종승인할 수 없다.

    마감이 "이 회차의 작업은 여기까지"를 확정하는 절차이므로, 그 전에 승인하면
    승인 후에도 내용이 바뀔 수 있다.
    """
    db, tok = _ctx()
    try:
        assessor = _user(db, "assessor-fa@acme.example", "최종평가자")
        _, ctrl = _control(db, "FA1", freq="annual")
        _assign(db, ctrl, "assessor", assessor)
        admin = db.query(User).filter(User.email == "admin@acme.example").one()
        if db.query(UserRole).filter(UserRole.user_id == admin.id,
                                     UserRole.role_name == "icfr_manager").first() is None:
            db.add(UserRole(user_id=admin.id, role_name="icfr_manager"))
            db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()

    ah = _headers(client, "assessor-fa@acme.example", "pw123456")
    mh = _headers(client)
    cycle = client.post("/api/assessment/cycles", headers=ah, json={
        "kind": "operation", "frequency": "annual", "name": "2026 최종승인검증",
        "fiscal_year": 2026, "period_index": 1}).json()

    early = client.post(f"/api/assessment/cycles/{cycle['id']}/approve", headers=mh)
    assert early.status_code == 409, early.text
    assert "마감되지 않은" in early.json()["detail"]

    client.post(f"/api/assessment/cycles/{cycle['id']}/close", headers=ah,
                json={"incomplete_reason": "검증용"})
    approved = client.post(f"/api/assessment/cycles/{cycle['id']}/approve", headers=mh)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by_name"] == "System Administrator"


# ── §5-8·9 부서승인 스킵 두 경로 ──────────────────────────

def test_dept_approval_skipped_control_rejects_approval(client: TestClient) -> None:
    """§5-8 — `dept_approval_skipped` 인 통제는 부서승인 단계를 건너뛴다.

    없는 단계에 승인 기록을 만들면 그 회차가 무엇을 거쳤는지 왜곡되므로 409 로 막는다.
    """
    db, tok = _ctx()
    try:
        boss = _user(db, "boss-sk@acme.example", "팀장겸책임자")
        _, ctrl = _control(db, "SK1", freq="annual")
        dept = Department(name="자금팀-SK", manager_id=boss)
        db.add(dept)
        db.flush()
        db.add(UserDepartment(user_id=boss, department_id=dept.id, is_primary=True))
        _assign(db, ctrl, "control_owner", boss)
        _assign(db, ctrl, "assessor", boss)
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()

    bh = _headers(client, "boss-sk@acme.example", "pw123456")
    cycle = client.post("/api/assessment/cycles", headers=bh, json={
        "kind": "operation", "frequency": "annual", "name": "2026 부서승인스킵",
        "fiscal_year": 2026, "period_index": 1}).json()
    act = client.post(f"/api/assessment/cycles/{cycle['id']}/activities", headers=bh, json={
        "control_id": str(ctrl), "activity_kind": "test"})
    assert act.status_code == 201, act.text

    resp = client.post(f"/api/assessment/activities/{act.json()['id']}/approvals",
                       headers=bh, json={"stage": "dept"})
    assert resp.status_code == 409, resp.text
    assert "부서 책임자를 겸해" in resp.json()["detail"]


def test_dept_approval_disabled_by_policy(client: TestClient) -> None:
    """§5-9 — 정책 토글이 false 면 **전체** 부서승인 스킵. 통제별 스킵과 다른 경로다."""
    db, tok = _ctx()
    try:
        owner = _user(db, "owner-pol@acme.example", "정책책임자")
        boss = _user(db, "boss-pol@acme.example", "정책팀장")
        _, ctrl = _control(db, "POL1", freq="annual")
        dept = Department(name="회계팀-POL", manager_id=boss)
        db.add(dept)
        db.flush()
        db.add(UserDepartment(user_id=owner, department_id=dept.id, is_primary=True))
        _assign(db, ctrl, "control_owner", owner)
        _assign(db, ctrl, "assessor", owner)
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()

    db2, tok2 = _ctx()
    try:
        _grant_icfr_manager(db2)
    finally:
        reset_active_tenant(tok2)
        db2.close()
    h = _headers(client)
    oh = _headers(client, "owner-pol@acme.example", "pw123456")
    resp = client.put("/api/org/policies", headers=h, json={
        "policy_key": "dept_approval_enabled", "policy_value": "false"})
    assert resp.status_code == 200, resp.text
    try:
        cycle = client.post("/api/assessment/cycles", headers=oh, json={
            "kind": "operation", "frequency": "annual", "name": "2026 정책스킵",
            "fiscal_year": 2026, "period_index": 1}).json()
        act = client.post(f"/api/assessment/cycles/{cycle['id']}/activities", headers=oh, json={
            "control_id": str(ctrl), "activity_kind": "test"}).json()
        denied = client.post(f"/api/assessment/activities/{act['id']}/approvals",
                             headers=oh, json={"stage": "dept"})
        assert denied.status_code == 409, denied
        assert "비활성화" in denied.json()["detail"]
    finally:
        client.put("/api/org/policies", headers=h, json={
            "policy_key": "dept_approval_enabled", "policy_value": "true"})


# ── §5-12 external_auditor ────────────────────────────────

def test_external_auditor_cannot_write(client: TestClient) -> None:
    """§5-12 — `external_auditor` 는 회차 생성·활동 기록을 할 수 없다(조회 전용)."""
    db, tok = _ctx()
    try:
        ext = _user(db, "ext-a@acme.example", "외부감사인A")
        if db.query(UserRole).filter(UserRole.user_id == ext,
                                     UserRole.role_name == "external_auditor").first() is None:
            db.add(UserRole(user_id=ext, role_name="external_auditor"))
            db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()

    eh = _headers(client, "ext-a@acme.example", "pw123456")
    resp = client.post("/api/assessment/cycles", headers=eh, json={
        "kind": "operation", "frequency": "annual", "name": "외부감사인회차",
        "fiscal_year": 2026, "period_index": 1})
    assert resp.status_code == 403, resp.text
    assert "외부감사인" in resp.json()["detail"]
    assert client.get("/api/assessment/cycles", headers=eh).status_code == 200


# ── §5-13 테넌트 격리 (sqlite 한계 명시) ──────────────────

def test_cycles_are_tenant_scoped(client: TestClient) -> None:
    """§5-13(부분) — 다른 테넌트의 회차가 조회되지 않는다.

    **ORM 자동 격리(ADR-0025) 레벨은 sqlite 에서도 유효하다.**
    복합 FK 교차 테넌트 거부는 sqlite 가 FK 를 강제하지 않아 검증할 수 없다 —
    postgres 에서 확인한다(ADR-0030 때와 같음).
    """
    from app.models.tenant import Tenant

    db, tok = _ctx()
    try:
        assessor = _user(db, "assessor-iso@acme.example", "격리평가자")
        _, ctrl = _control(db, "ISO1", freq="annual")
        _assign(db, ctrl, "assessor", assessor)
    finally:
        reset_active_tenant(tok)
        db.close()

    ah = _headers(client, "assessor-iso@acme.example", "pw123456")
    client.post("/api/assessment/cycles", headers=ah, json={
        "kind": "operation", "frequency": "annual", "name": "A사 회차-ISO",
        "fiscal_year": 2026, "period_index": 1})

    db = TestingSessionLocal()
    try:
        other = db.query(Tenant).filter(Tenant.code == "TENANT_ASSESS_B").first()
        if other is None:
            other = Tenant(name="회사B-회차", code="TENANT_ASSESS_B", is_active=True)
            db.add(other)
            db.commit()
        tok2 = set_active_tenant(other.id)
        try:
            names = {c.name for c in db.query(AssessmentCycle).all()}
            assert "A사 회차-ISO" not in names
        finally:
            reset_active_tenant(tok2)
    finally:
        db.close()


def test_activity_kind_must_match_cycle_kind(client: TestClient) -> None:
    """설계 활동은 design 회차에만 — 회차 종류가 다르면 409.

    ADR-0032 §2.2 가 두 회차를 독립으로 둔 것의 귀결이다. 섞이면 "이 회차가 무엇을
    평가했는가"가 흐려진다.
    """
    db, tok = _ctx()
    try:
        assessor = _user(db, "assessor-k@acme.example", "종류평가자")
        _, ctrl = _control(db, "K1", freq="annual")
        _assign(db, ctrl, "assessor", assessor)
    finally:
        reset_active_tenant(tok)
        db.close()

    ah = _headers(client, "assessor-k@acme.example", "pw123456")
    cycle = client.post("/api/assessment/cycles", headers=ah, json={
        "kind": "operation", "frequency": "annual", "name": "2026 종류검증",
        "fiscal_year": 2026, "period_index": 1}).json()
    resp = client.post(f"/api/assessment/cycles/{cycle['id']}/activities", headers=ah, json={
        "control_id": str(ctrl), "activity_kind": "design_assessment"})
    assert resp.status_code == 409, resp.text
    assert "design 회차에만" in resp.json()["detail"]


def test_targets_snapshot_survives_frequency_change(client: TestClient) -> None:
    """대상은 **스냅샷**이다 — 회차 생성 후 주기를 바꿔도 대상이 달라지지 않는다.

    감사가 "그때 무엇이 대상이었는가"를 묻고, 계산이면 과거 회차가 사후에 바뀐다.
    """
    h = _headers(client)
    db, tok = _ctx()
    try:
        assessor = _user(db, "assessor-sn@acme.example", "스냅평가자")
        _, ctrl = _control(db, "SN1", freq="annual")
        _assign(db, ctrl, "assessor", assessor)
    finally:
        reset_active_tenant(tok)
        db.close()

    ah = _headers(client, "assessor-sn@acme.example", "pw123456")
    cycle = client.post("/api/assessment/cycles", headers=ah, json={
        "kind": "operation", "frequency": "annual", "name": "2026 스냅샷검증",
        "fiscal_year": 2026, "period_index": 1}).json()

    before = client.get(f"/api/assessment/cycles/{cycle['id']}/targets",
                        headers=ah, params={"limit": 500}).json()
    assert str(ctrl) in {t["control_id"] for t in before["items"]}

    # 주기를 바꿔도 이미 만든 회차의 대상은 그대로다
    client.patch(f"/api/rcm/controls/{ctrl}",
                 json={"assessment_frequency": "monthly"}, headers=h)
    after = client.get(f"/api/assessment/cycles/{cycle['id']}/targets",
                       headers=ah, params={"limit": 500}).json()
    assert str(ctrl) in {t["control_id"] for t in after["items"]}
    assert before["total"] == after["total"]
