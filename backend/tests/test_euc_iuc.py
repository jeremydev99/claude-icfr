"""EUC·IUC 인벤토리 검증 (5-1, ADR-0033 정정).

**핵심은 두 가지다**(5-1 §5 — 2·3번):
- **공유** — 한 EUC 파일을 두 통제의 정보 항목이 참조해도 파일은 1건이다. 이 테스트가 없으면
  통제 중심 구조(정정 전 초안)로 만들어도 통과한다
- **산출** — 파일 중요성은 연결된 정보 항목 중 최고값이고, 하나를 올리면 위험 등급이 따라 바뀐다

사전 상태(통제 체인·계정)만 직접 넣고 **검증 대상 동작은 전부 HTTP 로 부른다** — 역할 테스트가
DB 직접 삽입만 해서 API 결함을 놓쳤던 13.9-35 의 교훈이다.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.core.tenant_context import DEFAULT_TENANT_ID, reset_active_tenant, set_active_tenant
from app.models.rcm_baseline import (
    BaselineControl,
    BaselineProcess,
    BaselineRisk,
    BaselineSubProcess,
    ControlInstance,
)
from app.models.tenant import UserTenantAccess
from app.models.user import User
from app.models.user_mgmt import UserRole
from tests.conftest import TestingSessionLocal

PW = "pw123456"


def _db():
    db = TestingSessionLocal()
    return db, set_active_tenant(DEFAULT_TENANT_ID)


def _close(db, tok) -> None:
    reset_active_tenant(tok)
    db.close()


def _account(email: str, roles: tuple[str, ...] = ()) -> str:
    db, tok = _db()
    try:
        u = db.query(User).filter(User.email == email).first()
        if u is None:
            u = User(email=email, hashed_password=hash_password(PW),
                     display_name=email.split("@")[0], role="user", is_active=True)
            db.add(u)
            db.commit()
        if db.query(UserTenantAccess).filter(
            UserTenantAccess.user_id == u.id, UserTenantAccess.tenant_id == DEFAULT_TENANT_ID,
        ).first() is None:
            db.add(UserTenantAccess(user_id=u.id, tenant_id=DEFAULT_TENANT_ID, role="user"))
            db.commit()
        for r in roles:
            if db.query(UserRole).filter(
                UserRole.user_id == u.id, UserRole.role_name == r,
                UserRole.is_deleted == False,  # noqa: E712
            ).first() is None:
                db.add(UserRole(user_id=u.id, role_name=r))
        db.commit()
        return str(u.id)
    finally:
        _close(db, tok)


def _headers(client: TestClient, email: str) -> dict:
    resp = client.post("/api/auth/login", data={"username": email, "password": PW})
    assert resp.status_code == 200, resp.text
    return {"Authorization": "Bearer " + resp.json()["access_token"]}


def _control(tag: str) -> str:
    """baseline 4단 체인 → 통제 id(정체성 id = baseline id)."""
    db, tok = _db()
    try:
        p = BaselineProcess(code=f"EI{tag}-P", name="P")
        db.add(p)
        db.flush()
        sp = BaselineSubProcess(code=f"EI{tag}-SP", name="SP", process_id=p.id)
        db.add(sp)
        db.flush()
        r = BaselineRisk(code=f"EI{tag}-R", description="R", assessment_level="LR", sub_process_id=sp.id)
        db.add(r)
        db.flush()
        c = BaselineControl(code=f"EI{tag}-C", name=f"통제{tag}", risk_id=r.id)
        db.add(c)
        db.commit()
        return str(c.id)
    finally:
        _close(db, tok)


def _set_excluded(control_id: str, excluded: bool) -> None:
    """overlay 로 통제 제외/복원. 복원은 instance 를 adopt 로 되돌린다."""
    db, tok = _db()
    try:
        inst = db.query(ControlInstance).filter(
            ControlInstance.baseline_control_id == uuid.UUID(control_id),
            ControlInstance.is_deleted == False,  # noqa: E712
        ).first()
        if inst is None:
            inst = ControlInstance(baseline_control_id=uuid.UUID(control_id), action="adopt")
            db.add(inst)
        inst.action = "exclude" if excluded else "adopt"
        db.commit()
    finally:
        _close(db, tok)


@pytest.fixture()
def mgr(client: TestClient) -> dict:
    _account("euc-mgr@acme.example", ("icfr_manager",))
    return _headers(client, "euc-mgr@acme.example")


def _file(client: TestClient, h: dict, name: str, **extra) -> dict:
    r = client.post("/api/euc/files", headers=h, json={"name": name, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _item(client: TestClient, h: dict, control_id: str, name: str, **extra) -> dict:
    r = client.post("/api/iuc/items", headers=h, json={"control_id": control_id, "name": name, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _file_view(client: TestClient, h: dict, file_id: str) -> dict:
    r = client.get(f"/api/euc/files/{file_id}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


# ── 핵심 ① 공유 ────────────────────────────────────────────

def test_one_file_shared_by_two_controls_stays_one(client: TestClient, mgr: dict) -> None:
    """**정정의 핵심.** 두 통제의 정보 항목이 같은 파일을 가리켜도 파일은 1건이고,
    파일 쪽에서 두 통제가 모두 보인다."""
    c1, c2 = _control("S1"), _control("S2")
    f = _file(client, mgr, "공유계산파일")
    _item(client, mgr, c1, "공유계산파일", euc_file_id=f["id"], importance="L")
    _item(client, mgr, c2, "공유계산파일", euc_file_id=f["id"], importance="L")

    files = [x for x in client.get("/api/euc/files", headers=mgr).json()["items"]
             if x["name"] == "공유계산파일"]
    assert len(files) == 1
    assert {c["id"] for c in files[0]["controls"]} == {c1, c2}


# ── 핵심 ② 산출 ────────────────────────────────────────────

def test_file_importance_is_max_of_items_and_drives_risk(client: TestClient, mgr: dict) -> None:
    """파일 중요성 = 연결된 정보 항목 중 최고값. 하나를 L→H 로 올리면 위험 등급이 따라 바뀐다."""
    c1, c2 = _control("M1"), _control("M2")
    f = _file(client, mgr, "최고값파일", complexity="formula")
    i1 = _item(client, mgr, c1, "최고값파일", euc_file_id=f["id"], importance="L")
    _item(client, mgr, c2, "최고값파일", euc_file_id=f["id"], importance="L")

    v = _file_view(client, mgr, f["id"])
    assert (v["importance"], v["risk_grade"]) == ("L", "low")

    assert client.patch(f"/api/iuc/items/{i1['id']}", headers=mgr,
                        json={"importance": "H"}).status_code == 200
    v = _file_view(client, mgr, f["id"])
    assert (v["importance"], v["risk_grade"], v["identified"]) == ("H", "high", True)


@pytest.mark.parametrize("complexity,importance,expected", [
    ("simple", "L", "low"), ("simple", "M", "low"), ("simple", "H", "moderate"),
    ("formula", "L", "low"), ("formula", "M", "moderate"), ("formula", "H", "high"),
    ("macro_model", "L", "moderate"), ("macro_model", "M", "high"), ("macro_model", "H", "high"),
])
def test_risk_matrix(client: TestClient, mgr: dict, complexity: str, importance: str,
                     expected: str) -> None:
    """복잡도 × 중요성 → 5-1 §2.2 초기 매트릭스 그대로."""
    tag = f"X{complexity[:2]}{importance}"
    c = _control(tag)
    f = _file(client, mgr, f"매트릭스-{tag}", complexity=complexity)
    _item(client, mgr, c, f"매트릭스-{tag}", euc_file_id=f["id"], importance=importance)
    assert _file_view(client, mgr, f["id"])["risk_grade"] == expected


def test_unevaluated_is_not_low(client: TestClient, mgr: dict) -> None:
    """복잡도가 없으면 위험 등급은 **미평가(null)** 다. Low 로 채우지 않는다 —
    원천이 Low 로 적은 것과 우리가 평가하지 않은 것은 다른 상태다."""
    c = _control("U1")
    f = _file(client, mgr, "미평가파일")
    _item(client, mgr, c, "미평가파일", euc_file_id=f["id"], importance="L")
    v = _file_view(client, mgr, f["id"])
    assert v["risk_grade"] is None and v["identified"] is None


# ── 임계값 ─────────────────────────────────────────────────

def test_threshold_is_a_policy_not_hardcoded(client: TestClient, mgr: dict) -> None:
    """moderate 파일은 기본 임계값(moderate)에서 식별 대상이고, 임계값을 high 로 올리면 빠진다."""
    c = _control("T1")
    f = _file(client, mgr, "임계값파일", complexity="simple")
    _item(client, mgr, c, "임계값파일", euc_file_id=f["id"], importance="H")  # simple×H = moderate
    try:
        assert _file_view(client, mgr, f["id"])["identified"] is True
        r = client.put("/api/org/policies", headers=mgr,
                       json={"policy_key": "euc_identification_threshold", "policy_value": "high"})
        assert r.status_code == 200, r.text
        assert _file_view(client, mgr, f["id"])["identified"] is False
    finally:
        client.put("/api/org/policies", headers=mgr,
                   json={"policy_key": "euc_identification_threshold", "policy_value": "moderate"})


def test_threshold_rejects_unknown_value(client: TestClient, mgr: dict) -> None:
    """목록 밖 임계값은 저장 시 422 — 저장되면 판정이 조용히 기본값으로 떨어진다."""
    r = client.put("/api/org/policies", headers=mgr,
                   json={"policy_key": "euc_identification_threshold", "policy_value": "Medium"})
    assert r.status_code == 422, r.text


# ── 값 목록 ────────────────────────────────────────────────

def test_change_frequency_options_are_euc_specific(client: TestClient, mgr: dict) -> None:
    """파일변경주기 선택지에 E·S·건별이 있다 — RCM 수행주기(O/D/W/M/Q/A)를 재사용하지 않았다."""
    meta = client.get("/api/euc/meta", headers=mgr).json()
    values = [o["value"] for o in meta["change_frequency"]]
    assert {"E", "S", "adhoc"} <= set(values)
    assert "O" not in values


def test_summary_shows_zero_buckets_and_unevaluated(client: TestClient, mgr: dict) -> None:
    """대시보드 집계는 0 건 칸도 내고, 미평가를 따로 센다(13.9-40)."""
    s = client.get("/api/euc/summary", headers=mgr).json()
    assert [b["value"] for b in s["risk_grade"]] == ["low", "moderate", "high", "__none__"]
    assert [b["value"] for b in s["importance"]] == ["H", "M", "L", "__none__"]
    assert s["unevaluated"] == next(b["count"] for b in s["risk_grade"] if b["value"] == "__none__")
    assert sum(b["count"] for b in s["risk_grade"]) == s["file_total"]


def test_source_rating_mismatch_is_flagged(client: TestClient, mgr: dict) -> None:
    """원천 참고값과 산출 등급이 **둘 다 있는데 다르면** 검토 신호로 표시된다."""
    from app.models.euc import EucFile
    c = _control("SR1")
    f = _file(client, mgr, "원천비교파일", complexity="formula")
    db, tok = _db()
    try:
        db.query(EucFile).filter(EucFile.id == uuid.UUID(f["id"])).one().source_risk_rating = "low"
        db.commit()
    finally:
        _close(db, tok)
    _item(client, mgr, c, "원천비교파일", euc_file_id=f["id"], importance="H")  # formula×H = high
    assert _file_view(client, mgr, f["id"])["source_mismatch"] is True


# ── 통제 제외 (2026-09-22 정정) ────────────────────────────

def test_excluded_control_drops_item_and_restore_brings_it_back(
    client: TestClient, mgr: dict,
) -> None:
    """통제를 제외하면 그 항목이 IUC 목록과 파일 중요성 계산에서 빠지고, 복원하면 돌아온다.
    물리적으로는 건드리지 않는다(ADR-0029 §2.4 와 같은 원칙)."""
    c_hi, c_lo = _control("E1"), _control("E2")
    f = _file(client, mgr, "제외계산파일", complexity="formula")
    hi = _item(client, mgr, c_hi, "제외계산파일", euc_file_id=f["id"], importance="H")
    _item(client, mgr, c_lo, "제외계산파일", euc_file_id=f["id"], importance="L")
    assert _file_view(client, mgr, f["id"])["importance"] == "H"

    _set_excluded(c_hi, True)
    ids = {i["id"] for i in client.get("/api/iuc/items", headers=mgr).json()["items"]}
    assert hi["id"] not in ids
    v = _file_view(client, mgr, f["id"])
    assert v["importance"] == "L" and v["risk_grade"] == "low"
    assert {c["id"] for c in v["controls"]} == {c_lo}

    _set_excluded(c_hi, False)
    ids = {i["id"] for i in client.get("/api/iuc/items", headers=mgr).json()["items"]}
    assert hi["id"] in ids
    assert _file_view(client, mgr, f["id"])["importance"] == "H"


def test_file_whose_controls_are_all_excluded_stays(client: TestClient, mgr: dict) -> None:
    """참조 통제가 전부 제외돼도 파일은 지우지 않는다 — "참조 통제 0건"으로 보인다."""
    c = _control("E3")
    f = _file(client, mgr, "고아파일")
    _item(client, mgr, c, "고아파일", euc_file_id=f["id"], importance="M")
    _set_excluded(c, True)
    try:
        v = _file_view(client, mgr, f["id"])
        assert v["controls"] == [] and v["importance"] is None
    finally:
        _set_excluded(c, False)


# ── 권한 (5-1 §2.5) ────────────────────────────────────────

def test_control_owner_can_edit_only_own_control(client: TestClient, mgr: dict) -> None:
    """통제 A 의 책임자는 A 의 정보 항목은 고치고 B 의 것은 못 고친다(통제 단위 권한)."""
    owner = _account("euc-owner@acme.example")
    ca, cb = _control("P1"), _control("P2")
    ia = _item(client, mgr, ca, "A의정보", importance="L")
    ib = _item(client, mgr, cb, "B의정보", importance="L")
    assert client.post("/api/org/assignments", headers=mgr, json={
        "scope": "control", "target_id": ca, "role_name": "control_owner", "user_id": owner,
    }).status_code == 201

    oh = _headers(client, "euc-owner@acme.example")
    assert client.patch(f"/api/iuc/items/{ia['id']}", headers=oh, json={"importance": "M"}).status_code == 200
    assert client.patch(f"/api/iuc/items/{ib['id']}", headers=oh, json={"importance": "M"}).status_code == 403
    assert client.post("/api/iuc/items", headers=oh,
                       json={"control_id": cb, "name": "남의통제"}).status_code == 403


def test_plain_user_cannot_create_file(client: TestClient) -> None:
    """파일 생성은 icfr_manager 만 — `require_write` 였다면 일반 사용자가 통과한다."""
    _account("euc-plain@acme.example")
    r = client.post("/api/euc/files", headers=_headers(client, "euc-plain@acme.example"),
                    json={"name": "무단파일"})
    assert r.status_code == 403


def test_external_auditor_is_read_only(client: TestClient, mgr: dict) -> None:
    """external_auditor 는 모든 쓰기가 거부되고 조회는 된다."""
    c = _control("A1")
    f = _file(client, mgr, "감사인확인파일")
    i = _item(client, mgr, c, "감사인확인정보", euc_file_id=f["id"])
    _account("euc-ext@acme.example", ("external_auditor",))
    eh = _headers(client, "euc-ext@acme.example")

    assert client.get("/api/euc/files", headers=eh).status_code == 200
    assert client.get("/api/iuc/items", headers=eh).status_code == 200
    assert client.post("/api/euc/files", headers=eh, json={"name": "x"}).status_code == 403
    assert client.patch(f"/api/euc/files/{f['id']}", headers=eh, json={"complexity": "simple"}).status_code == 403
    assert client.post("/api/iuc/items", headers=eh, json={"control_id": c, "name": "x"}).status_code == 403
    assert client.patch(f"/api/iuc/items/{i['id']}", headers=eh, json={"importance": "H"}).status_code == 403
    assert client.delete(f"/api/iuc/items/{i['id']}", headers=eh).status_code == 403


# ── 재생성 (부분 유니크) ───────────────────────────────────

def test_recreate_after_delete(client: TestClient, mgr: dict) -> None:
    """지웠다가 같은 키로 다시 만들 수 있다 — 처음부터 부분 유니크(13.9-35 ④·13.9-42)."""
    c = _control("R1")
    i = _item(client, mgr, c, "재생성정보")
    assert client.delete(f"/api/iuc/items/{i['id']}", headers=mgr).status_code == 204
    _item(client, mgr, c, "재생성정보")

    f = _file(client, mgr, "재생성파일")
    assert client.delete(f"/api/euc/files/{f['id']}", headers=mgr).status_code == 204
    _file(client, mgr, "재생성파일")


def test_live_duplicate_gets_readable_message(client: TestClient, mgr: dict) -> None:
    _file(client, mgr, "중복파일")
    r = client.post("/api/euc/files", headers=mgr, json={"name": "중복파일"})
    assert r.status_code == 409 and "중복파일" in r.json()["detail"]


def test_referenced_file_cannot_be_deleted(client: TestClient, mgr: dict) -> None:
    """정보 항목이 가리키는 파일은 지우지 않는다 — 제외된 통제의 항목도 센다."""
    c = _control("D1")
    f = _file(client, mgr, "참조중파일")
    _item(client, mgr, c, "참조중정보", euc_file_id=f["id"])
    r = client.delete(f"/api/euc/files/{f['id']}", headers=mgr)
    assert r.status_code == 409 and "정보 항목" in r.json()["detail"]


# ── 테넌트 격리 ────────────────────────────────────────────

def test_other_tenant_files_are_invisible(client: TestClient, mgr: dict) -> None:
    """다른 테넌트의 EUC 파일은 목록에 나오지 않는다(ADR-0025 자동 격리).

    **DB 제약 수준(복합 FK 로 교차 참조 거부)은 sqlite 가 FK 를 강제하지 않아 여기서 볼 수
    없다** — postgres 에서 직접 확인했다(ClaudeICFR.md 13.9-45). 여기는 ORM 조회 격리만 본다.
    """
    from app.models.euc import EucFile
    from app.models.tenant import Tenant

    db = TestingSessionLocal()
    try:
        t = db.query(Tenant).filter(Tenant.code == "EUC_ISO_B").first()
        if t is None:
            t = Tenant(name="EUC격리B", code="EUC_ISO_B", is_active=True)
            db.add(t)
            db.commit()
        tok = set_active_tenant(t.id)
        try:
            if db.query(EucFile).filter(EucFile.name == "B사전용파일").first() is None:
                db.add(EucFile(name="B사전용파일"))
                db.commit()
        finally:
            reset_active_tenant(tok)
    finally:
        db.close()

    names = {f["name"] for f in client.get("/api/euc/files", headers=mgr).json()["items"]}
    assert "B사전용파일" not in names
