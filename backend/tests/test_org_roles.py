"""부서·역할 배정 검증 (3-1, ADR-0031).

**핵심은 두 가지다.**
- `test_same_user_different_roles_per_control` (§6-4) — 역할이 사람이 아니라 통제에
  붙는지. 이게 없으면 사람 단위 RBAC 으로 만들어도 나머지가 전부 통과한다.
- `test_conflict_requires_reason` (§6-8) — 막지 않고 기록하는지(§2.5).

sqlite 에서 유효한 것과 아닌 것을 구분해 둔다. ORM·핸들러 레벨 검증은 그대로 유효하나
**복합 FK 로 인한 교차 테넌트 거부는 sqlite 가 FK 를 강제하지 않아 검증할 수 없다**
(ADR-0030 때와 같음). 그 항목은 postgres 에서 확인한다.
"""
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.models.org import Department
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


def _headers(client: TestClient) -> dict:
    resp = client.post("/api/auth/login",
                       data={"username": "admin@acme.example", "password": "admin123"})
    assert resp.status_code == 200
    return {"Authorization": "Bearer " + resp.json()["access_token"]}


def _make_user(db, email: str, name: str) -> UUID:
    """계정 + 활성 tenant 접근 권한. 접근이 없으면 로그인은 되어도 get_current_user 가
    "소속된 회사(tenant)가 없습니다" 로 막는다."""
    u = db.query(User).filter(User.email == email).first()
    if u is None:
        u = User(email=email, hashed_password=hash_password("pw123456"),
                 display_name=name, role="user", is_active=True)
        db.add(u)
        db.commit()
    access = db.query(UserTenantAccess).filter(
        UserTenantAccess.user_id == u.id,
        UserTenantAccess.tenant_id == DEFAULT_TENANT_ID,
    ).first()
    if access is None:
        db.add(UserTenantAccess(user_id=u.id, tenant_id=DEFAULT_TENANT_ID, role="user"))
        db.commit()
    return u.id


def _chain(db, suffix: str) -> tuple[UUID, UUID]:
    """baseline 4단 체인 → (process_id, control_id). 활성 tenant 안에서 호출할 것."""
    p = BaselineProcess(code=f"OR{suffix}-P", name="P")
    db.add(p)
    db.flush()
    sp = BaselineSubProcess(code=f"OR{suffix}-SP", name="SP", process_id=p.id)
    db.add(sp)
    db.flush()
    r = BaselineRisk(code=f"OR{suffix}-R", description="R", assessment_level="LR",
                     sub_process_id=sp.id)
    db.add(r)
    db.flush()
    c = BaselineControl(code=f"OR{suffix}-C", name="C", risk_id=r.id, owner_name="문서상수행자")
    db.add(c)
    db.commit()
    return p.id, c.id


@pytest.fixture
def org_ctx(client: TestClient):
    """(headers, db 조작용 컨텍스트) — 테스트마다 활성 tenant 를 걸고 정리한다."""
    h = _headers(client)
    db = TestingSessionLocal()
    tok = set_active_tenant(DEFAULT_TENANT_ID)
    try:
        yield h, db
    finally:
        reset_active_tenant(tok)
        db.close()


# ── §6-1·2·3 부서·소속 ────────────────────────────────────

def test_user_can_belong_to_multiple_departments(client: TestClient, org_ctx) -> None:
    """§6-1 — 한 사용자가 여러 부서에 소속 가능. 회계팀 직원이 전담팀을 겸한다."""
    h, db = org_ctx
    uid = str(_make_user(db, "multi@acme.example", "다중소속"))
    d1 = client.post("/api/org/departments", json={"name": "회계팀-M1"}, headers=h).json()
    d2 = client.post("/api/org/departments", json={"name": "내부회계전담팀-M1"}, headers=h).json()

    for d in (d1, d2):
        resp = client.post("/api/org/memberships", headers=h,
                           json={"user_id": uid, "department_id": d["id"]})
        assert resp.status_code == 201, resp.text

    body = client.get("/api/org/memberships", params={"user_id": uid}, headers=h).json()
    assert body["total"] == 2


def test_primary_department_is_exactly_one(client: TestClient, org_ctx) -> None:
    """§6-2 — 주 소속은 정확히 하나. 두 번째를 주 소속으로 지정하면 첫 번째가 해제된다.

    `dept_approver` 유도의 기준이므로 둘이면 어느 부서 책임자를 쓸지 정할 수 없다.
    """
    h, db = org_ctx
    uid = str(_make_user(db, "primary@acme.example", "주소속"))
    d1 = client.post("/api/org/departments", json={"name": "자금팀-P1"}, headers=h).json()
    d2 = client.post("/api/org/departments", json={"name": "회계팀-P1"}, headers=h).json()

    client.post("/api/org/memberships", headers=h,
                json={"user_id": uid, "department_id": d1["id"], "is_primary": True})
    client.post("/api/org/memberships", headers=h,
                json={"user_id": uid, "department_id": d2["id"], "is_primary": True})

    items = client.get("/api/org/memberships", params={"user_id": uid}, headers=h).json()["items"]
    primaries = [m for m in items if m["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["department_id"] == d2["id"]


def test_user_can_manage_multiple_departments(client: TestClient, org_ctx) -> None:
    """§6-3 — 한 사용자가 여러 부서의 책임자. 본부장이 팀장 퇴사 시 겸임하는 경우."""
    h, db = org_ctx
    uid = str(_make_user(db, "manager@acme.example", "겸임본부장"))
    for name in ("개발1팀-G1", "개발2팀-G1"):
        resp = client.post("/api/org/departments", headers=h,
                           json={"name": name, "manager_id": uid})
        assert resp.status_code == 201, resp.text

    items = client.get("/api/org/departments", params={"limit": 500}, headers=h).json()["items"]
    managed = [d for d in items if d["manager_id"] == uid]
    assert len(managed) == 2
    assert all(d["manager_name"] == "겸임본부장" for d in managed)


def test_department_name_duplicate_rejected(client: TestClient, org_ctx) -> None:
    """부서명 중복은 409 + 의미 있는 메시지(IntegrityError 일반 문구가 아니다)."""
    h, _ = org_ctx
    assert client.post("/api/org/departments", json={"name": "중복팀-D1"},
                       headers=h).status_code == 201
    resp = client.post("/api/org/departments", json={"name": "중복팀-D1"}, headers=h)
    assert resp.status_code == 409
    assert "이미 사용 중" in resp.json()["detail"]


def test_department_delete_blocked_when_members_remain(client: TestClient, org_ctx) -> None:
    """소속 인원이 남은 부서는 삭제 거부 — 소속만 남으면 어느 부서인지 알 수 없다."""
    h, db = org_ctx
    uid = str(_make_user(db, "member@acme.example", "소속자"))
    d = client.post("/api/org/departments", json={"name": "삭제대상팀-X1"}, headers=h).json()
    client.post("/api/org/memberships", headers=h,
                json={"user_id": uid, "department_id": d["id"]})

    resp = client.delete(f"/api/org/departments/{d['id']}", headers=h)
    assert resp.status_code == 409
    assert "소속 인원" in resp.json()["detail"]


# ── §6-4 핵심: 역할은 통제에 붙는다 ────────────────────────

def test_same_user_different_roles_per_control(client: TestClient, org_ctx) -> None:
    """§6-4 **핵심** — 같은 사용자가 통제 A에서 control_owner, 통제 B에서 assessor.

    관리부서가 4명인 회사에서 회계 담당이 회계 통제의 책임자이면서 인사 통제의
    평가자가 되는 상호 배정은 불가피하다(ADR-0031 §2.2). **역할을 사람 속성으로
    두면 이 구조를 표현할 수 없다** — 이 테스트가 없으면 사람 단위 RBAC 으로
    만들어도 나머지가 전부 통과한다.
    """
    h, db = org_ctx
    uid = str(_make_user(db, "dual@acme.example", "겸직자"))
    _, ctrl_a = _chain(db, "A1")
    _, ctrl_b = _chain(db, "B1")

    for target, role in ((ctrl_a, "control_owner"), (ctrl_b, "assessor")):
        resp = client.post("/api/org/assignments", headers=h, json={
            "scope": "control", "target_id": str(target), "role_name": role, "user_id": uid,
        })
        assert resp.status_code == 201, resp.text

    roles_a = client.get(f"/api/org/controls/{ctrl_a}/roles", headers=h).json()["roles"]
    roles_b = client.get(f"/api/org/controls/{ctrl_b}/roles", headers=h).json()["roles"]
    owner_a = next(r for r in roles_a if r["role_name"] == "control_owner")
    assessor_b = next(r for r in roles_b if r["role_name"] == "assessor")
    assert owner_a["user_id"] == uid
    assert assessor_b["user_id"] == uid
    # 반대쪽에는 배정되지 않았다
    assert next(r for r in roles_a if r["role_name"] == "assessor")["user_id"] is None


# ── §6-5·6·7 기본값 + 예외 + 출처 ─────────────────────────

def test_process_default_applies_to_controls(client: TestClient, org_ctx) -> None:
    """§6-5 — 프로세스 기본값이 개별 지정 없는 통제에 자동 반영된다."""
    h, db = org_ctx
    uid = str(_make_user(db, "procdefault@acme.example", "기본배정자"))
    proc_id, ctrl_id = _chain(db, "D1")

    resp = client.post("/api/org/assignments", headers=h, json={
        "scope": "process", "target_id": str(proc_id),
        "role_name": "assessor", "user_id": uid,
    })
    assert resp.status_code == 201, resp.text

    roles = client.get(f"/api/org/controls/{ctrl_id}/roles", headers=h).json()["roles"]
    assessor = next(r for r in roles if r["role_name"] == "assessor")
    assert assessor["user_id"] == uid
    assert assessor["source"] == "process"          # §6-7 출처 구분
    assert assessor["source_id"] == str(proc_id)


def test_control_override_beats_process_default(client: TestClient, org_ctx) -> None:
    """§6-6·7 — 통제별 지정이 프로세스 기본값을 이기고, 출처가 구분된다."""
    h, db = org_ctx
    base = str(_make_user(db, "base@acme.example", "기본"))
    over = str(_make_user(db, "override@acme.example", "예외"))
    proc_id, ctrl_id = _chain(db, "E1")

    client.post("/api/org/assignments", headers=h, json={
        "scope": "process", "target_id": str(proc_id),
        "role_name": "assessor", "user_id": base})
    client.post("/api/org/assignments", headers=h, json={
        "scope": "control", "target_id": str(ctrl_id),
        "role_name": "assessor", "user_id": over})

    roles = client.get(f"/api/org/controls/{ctrl_id}/roles", headers=h).json()["roles"]
    assessor = next(r for r in roles if r["role_name"] == "assessor")
    assert assessor["user_id"] == over
    assert assessor["source"] == "control"
    assert assessor["source_id"] == str(ctrl_id)


def test_owner_name_is_provided_as_reference(client: TestClient, org_ctx) -> None:
    """§2.4 — owner_name 을 이관하지 않고 참고 정보로 함께 싣는다.

    배정과 어긋나면 그 자체가 검토 대상이 된다.
    """
    h, db = org_ctx
    _, ctrl_id = _chain(db, "F1")
    body = client.get(f"/api/org/controls/{ctrl_id}/roles", headers=h).json()
    assert body["owner_name"] == "문서상수행자"
    assert body["control_code"] == "ORF1-C"


# ── §6-8·9 이해상충 ───────────────────────────────────────

def test_conflict_requires_reason(client: TestClient, org_ctx) -> None:
    """§6-8 **핵심** — control_owner = assessor 는 사유 없으면 거부, 있으면 저장.

    **막지 않고 기록한다**(§2.5). 막으면 중소기업이 시스템을 쓸 수 없고,
    조용히 허용하면 감사에서 지적된다. 사유가 보완통제 증적이 된다.
    """
    h, db = org_ctx
    uid = str(_make_user(db, "conflict@acme.example", "겸직발생"))
    _, ctrl_id = _chain(db, "G1")

    client.post("/api/org/assignments", headers=h, json={
        "scope": "control", "target_id": str(ctrl_id),
        "role_name": "control_owner", "user_id": uid})

    without = client.post("/api/org/assignments", headers=h, json={
        "scope": "control", "target_id": str(ctrl_id),
        "role_name": "assessor", "user_id": uid})
    assert without.status_code == 409, without.text
    assert "사유" in without.json()["detail"]

    with_reason = client.post("/api/org/assignments", headers=h, json={
        "scope": "control", "target_id": str(ctrl_id), "role_name": "assessor",
        "user_id": uid, "conflict_reason": "인원 4명으로 분리 불가. 상급자 검토로 보완"})
    assert with_reason.status_code == 201, with_reason.text

    body = client.get(f"/api/org/controls/{ctrl_id}/roles", headers=h).json()
    assert "assessor=control_owner" in body["conflicts"]


def test_conflict_reason_is_recorded_as_history(client: TestClient, org_ctx) -> None:
    """§6-8 — 사유가 이력으로 남는다. 감사에서 "왜 겸직을 허용했는가"의 답이다."""
    from app.models.role_assignment import ConflictAcknowledgement

    h, db = org_ctx
    uid = str(_make_user(db, "ack@acme.example", "사유기록"))
    _, ctrl_id = _chain(db, "H1")
    client.post("/api/org/assignments", headers=h, json={
        "scope": "control", "target_id": str(ctrl_id),
        "role_name": "control_owner", "user_id": uid})
    client.post("/api/org/assignments", headers=h, json={
        "scope": "control", "target_id": str(ctrl_id), "role_name": "assessor",
        "user_id": uid, "conflict_reason": "보완통제 문서화 완료"})

    db.expire_all()
    acks = db.query(ConflictAcknowledgement).filter(
        ConflictAcknowledgement.target_id == ctrl_id).all()
    assert len(acks) == 1
    assert acks[0].reason == "보완통제 문서화 완료"


def test_policy_toggle_blocks_conflict(client: TestClient, org_ctx) -> None:
    """§6-9 — 정책 토글을 금지로 전환하면 사유가 있어도 409 로 거부된다."""
    h, db = org_ctx
    uid = str(_make_user(db, "blocked@acme.example", "금지대상"))
    manager_id = _make_user(db, "icfrmgr@acme.example", "내부회계관리자")
    _, ctrl_id = _chain(db, "I1")

    admin = db.query(User).filter(User.email == "admin@acme.example").one()
    db.add(UserRole(user_id=admin.id, role_name="icfr_manager"))
    db.commit()
    assert manager_id is not None

    resp = client.put("/api/org/policies", headers=h, json={
        "policy_key": "conflict_assessor_control_owner_blocked", "policy_value": "true"})
    assert resp.status_code == 200, resp.text

    try:
        client.post("/api/org/assignments", headers=h, json={
            "scope": "control", "target_id": str(ctrl_id),
            "role_name": "control_owner", "user_id": uid})
        blocked = client.post("/api/org/assignments", headers=h, json={
            "scope": "control", "target_id": str(ctrl_id), "role_name": "assessor",
            "user_id": uid, "conflict_reason": "사유가 있어도 금지면 막힌다"})
        assert blocked.status_code == 409
        assert "정책상 금지" in blocked.json()["detail"]
    finally:
        # 정책은 **테넌트 전역 상태**다. 남기면 이후 테스트가 전부 "정책상 금지" 를 받는다
        # (공용 세션 DB 를 쓰므로). 켠 테스트가 되돌린다.
        client.put("/api/org/policies", headers=h, json={
            "policy_key": "conflict_assessor_control_owner_blocked",
            "policy_value": "false"})


# ── §6-10·11 dept_approver 유도 ───────────────────────────

def test_dept_approver_derived_from_primary_department(client: TestClient, org_ctx) -> None:
    """§6-10 — dept_approver 가 통제책임자의 주 소속 부서 책임자로 유도된다.

    배정 레코드가 없어도 값이 나오며 `source='derived'` 로 표시된다.
    """
    h, db = org_ctx
    owner = str(_make_user(db, "owner-d@acme.example", "통제책임자"))
    boss = str(_make_user(db, "boss-d@acme.example", "부서책임자"))
    _, ctrl_id = _chain(db, "J1")

    dept = client.post("/api/org/departments", headers=h,
                       json={"name": "자금팀-J1", "manager_id": boss}).json()
    client.post("/api/org/memberships", headers=h, json={
        "user_id": owner, "department_id": dept["id"], "is_primary": True})
    client.post("/api/org/assignments", headers=h, json={
        "scope": "control", "target_id": str(ctrl_id),
        "role_name": "control_owner", "user_id": owner})

    roles = client.get(f"/api/org/controls/{ctrl_id}/roles", headers=h).json()["roles"]
    approver = next(r for r in roles if r["role_name"] == "dept_approver")
    assert approver["user_id"] == boss
    assert approver["source"] == "derived"
    assert approver["source_id"] == dept["id"]


def test_explicit_dept_approver_beats_derivation(client: TestClient, org_ctx) -> None:
    """§6-11 — 통제별 개별 지정이 유도값보다 우선한다."""
    h, db = org_ctx
    owner = str(_make_user(db, "owner-k@acme.example", "책임자K"))
    boss = str(_make_user(db, "boss-k@acme.example", "유도대상"))
    explicit = str(_make_user(db, "explicit-k@acme.example", "명시지정"))
    _, ctrl_id = _chain(db, "K1")

    dept = client.post("/api/org/departments", headers=h,
                       json={"name": "회계팀-K1", "manager_id": boss}).json()
    client.post("/api/org/memberships", headers=h, json={
        "user_id": owner, "department_id": dept["id"], "is_primary": True})
    client.post("/api/org/assignments", headers=h, json={
        "scope": "control", "target_id": str(ctrl_id),
        "role_name": "control_owner", "user_id": owner})
    client.post("/api/org/assignments", headers=h, json={
        "scope": "control", "target_id": str(ctrl_id),
        "role_name": "dept_approver", "user_id": explicit})

    roles = client.get(f"/api/org/controls/{ctrl_id}/roles", headers=h).json()["roles"]
    approver = next(r for r in roles if r["role_name"] == "dept_approver")
    assert approver["user_id"] == explicit
    assert approver["source"] == "control"


# ── §6-12 external_auditor 조회 전용 ──────────────────────

def test_external_auditor_cannot_write(client: TestClient, org_ctx) -> None:
    """§6-12 — external_auditor 는 생성·수정 API 에서 거부된다(§2.1 조회 전용).

    외부감사인이 평가 데이터를 만들거나 고칠 수 있으면 독립성 훼손이다.
    """
    h, db = org_ctx
    ext_id = _make_user(db, "ext@acme.example", "외부감사인")
    db.add(UserRole(user_id=ext_id, role_name="external_auditor"))
    db.commit()

    ext_h = {"Authorization": "Bearer " + client.post(
        "/api/auth/login",
        data={"username": "ext@acme.example", "password": "pw123456"},
    ).json()["access_token"]}

    resp = client.post("/api/org/departments", json={"name": "외부감사인생성-Z1"}, headers=ext_h)
    assert resp.status_code == 403, resp.text
    assert "외부감사인" in resp.json()["detail"]

    # 조회는 가능하다
    assert client.get("/api/org/departments", headers=ext_h).status_code == 200


# ── §6-13 테넌트 격리 (sqlite 한계 명시) ──────────────────

def test_tenant_isolation_on_departments(client: TestClient, org_ctx) -> None:
    """§6-13(부분) — 다른 테넌트의 부서가 조회되지 않는다.

    **ORM 자동 격리(ADR-0025) 레벨은 sqlite 에서도 유효하다.**
    복합 FK 로 인한 교차 테넌트 참조 거부는 sqlite 가 FK 를 강제하지 않아
    여기서 검증할 수 없다 — postgres 에서 확인한다(ADR-0030 때와 같음).
    """
    from app.models.tenant import Tenant

    h, db = org_ctx
    client.post("/api/org/departments", json={"name": "A사부서-T1"}, headers=h)

    other = db.query(Tenant).filter(Tenant.code == "TENANT_ORG_B").first()
    if other is None:
        other = Tenant(name="회사B-org", code="TENANT_ORG_B", is_active=True)
        db.add(other)
        db.commit()

    reset_active_tenant(set_active_tenant(other.id))
    tok = set_active_tenant(other.id)
    try:
        names = {d.name for d in db.query(Department).all()}
        assert "A사부서-T1" not in names
    finally:
        reset_active_tenant(tok)


def test_role_assignment_is_tenant_scoped(client: TestClient, org_ctx) -> None:
    """§6-13(부분) — 배정도 자동 격리 대상이다."""
    h, db = org_ctx
    uid = str(_make_user(db, "iso@acme.example", "격리검증"))
    _, ctrl_id = _chain(db, "L1")
    client.post("/api/org/assignments", headers=h, json={
        "scope": "control", "target_id": str(ctrl_id),
        "role_name": "control_owner", "user_id": uid})

    from app.models.tenant import Tenant
    other = db.query(Tenant).filter(Tenant.code == "TENANT_ORG_C").first()
    if other is None:
        other = Tenant(name="회사C-org", code="TENANT_ORG_C", is_active=True)
        db.add(other)
        db.commit()

    tok = set_active_tenant(other.id)
    try:
        assert db.query(RoleAssignment).filter(
            RoleAssignment.target_id == ctrl_id).count() == 0
    finally:
        reset_active_tenant(tok)


# ── 부서승인 스킵 (2026-09-04 정정) ────────────────────────

def test_owner_who_is_dept_manager_is_not_a_conflict(client: TestClient, org_ctx) -> None:
    """통제책임자가 자기 부서의 책임자면 **충돌이 아니다** — 저장이 그대로 성공한다.

    2026-09-04 정정. 부서승인은 "상급자가 검토한다"는 뜻인데 통제책임자가 팀장
    본인이면 그 위 단계가 없다. 겸직이 아니라 단계가 없는 것이다(ADR-0031 §2.4 정정).
    **팀장이 통제책임자인 통제는 전부 이 형태라, 경고로 두면 대부분의 통제에
    사유 입력을 요구하게 된다.**
    """
    h, db = org_ctx
    boss = str(_make_user(db, "selfboss@acme.example", "팀장겸통제책임자"))
    _, ctrl_id = _chain(db, "S1")

    dept = client.post("/api/org/departments", headers=h,
                       json={"name": "자금팀-S1", "manager_id": boss}).json()
    client.post("/api/org/memberships", headers=h, json={
        "user_id": boss, "department_id": dept["id"], "is_primary": True})

    # 사유 없이 저장해도 201 — 충돌로 잡히지 않는다
    resp = client.post("/api/org/assignments", headers=h, json={
        "scope": "control", "target_id": str(ctrl_id),
        "role_name": "control_owner", "user_id": boss})
    assert resp.status_code == 201, resp.text

    body = client.get(f"/api/org/controls/{ctrl_id}/roles", headers=h).json()
    assert body["conflicts"] == []


def test_dept_approval_skipped_is_reported(client: TestClient, org_ctx) -> None:
    """스킵 상태가 해석 응답에 표시된다 — FE 가 "부서승인 없음"을 표시할 수 있어야 한다.

    스킵이어도 `roles[]` 의 dept_approver 는 남으며 `user_id` 가 control_owner 와
    같다 — 별도 승인자가 아니라는 뜻이다.
    """
    h, db = org_ctx
    boss = str(_make_user(db, "skipboss@acme.example", "팀장"))
    _, ctrl_id = _chain(db, "S2")

    dept = client.post("/api/org/departments", headers=h,
                       json={"name": "회계팀-S2", "manager_id": boss}).json()
    client.post("/api/org/memberships", headers=h, json={
        "user_id": boss, "department_id": dept["id"], "is_primary": True})
    client.post("/api/org/assignments", headers=h, json={
        "scope": "control", "target_id": str(ctrl_id),
        "role_name": "control_owner", "user_id": boss})

    body = client.get(f"/api/org/controls/{ctrl_id}/roles", headers=h).json()
    assert body["dept_approval_skipped"] is True
    approver = next(r for r in body["roles"] if r["role_name"] == "dept_approver")
    assert approver["user_id"] == boss          # control_owner 와 같은 사람
    assert approver["source"] == "derived"      # source 는 출처 의미를 유지한다


def test_dept_approval_not_skipped_when_approver_differs(client: TestClient, org_ctx) -> None:
    """통제책임자와 부서 책임자가 다르면 스킵이 아니다 — 회귀 가드."""
    h, db = org_ctx
    owner = str(_make_user(db, "owner-s3@acme.example", "담당자"))
    boss = str(_make_user(db, "boss-s3@acme.example", "팀장S3"))
    _, ctrl_id = _chain(db, "S3")

    dept = client.post("/api/org/departments", headers=h,
                       json={"name": "영업1팀-S3", "manager_id": boss}).json()
    client.post("/api/org/memberships", headers=h, json={
        "user_id": owner, "department_id": dept["id"], "is_primary": True})
    client.post("/api/org/assignments", headers=h, json={
        "scope": "control", "target_id": str(ctrl_id),
        "role_name": "control_owner", "user_id": owner})

    body = client.get(f"/api/org/controls/{ctrl_id}/roles", headers=h).json()
    assert body["dept_approval_skipped"] is False
    assert body["conflicts"] == []


def test_owner_assessor_conflict_still_detected(client: TestClient, org_ctx) -> None:
    """control_owner = assessor 는 **여전히 충돌**이다 — 이번 정정의 회귀 가드.

    dept_approver 조합만 제외했지 이해상충 판정 자체를 약화시킨 것이 아니다.
    """
    h, db = org_ctx
    uid = str(_make_user(db, "still@acme.example", "여전히충돌"))
    _, ctrl_id = _chain(db, "S4")

    client.post("/api/org/assignments", headers=h, json={
        "scope": "control", "target_id": str(ctrl_id),
        "role_name": "control_owner", "user_id": uid})
    resp = client.post("/api/org/assignments", headers=h, json={
        "scope": "control", "target_id": str(ctrl_id),
        "role_name": "assessor", "user_id": uid})
    assert resp.status_code == 409
    assert "사유" in resp.json()["detail"]
    assert "assessor=control_owner" in resp.json()["detail"]
