"""RCM 엑셀 갱신 업로드 (2026-10-08, 13.9-109) — 현재 RCM 대비 미리보기·회사 수정분 반영·엑셀에 없음 보존·잠금."""
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.core.tenant_context import reset_active_tenant, set_active_tenant
from app.models.rcm_baseline import (
    BaselineControl,
    BaselineControlAssertion,
    BaselineProcess,
    BaselineRisk,
    BaselineRiskCategory,
    BaselineSubProcess,
    ControlInstance,
)
from tests.conftest import TestingSessionLocal
from tests.test_governance import T

U = "/api/rcm/upload-excel"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _seed(t: T) -> None:
    """기준 RCM: P / P-010 / P-010-10 / 통제 2건(C1 담당 갑, C2 담당 을), 어서션 E·C, C1 에 E 연결."""
    db = TestingSessionLocal()
    tok = set_active_tenant(t.tid)
    try:
        cats = {}
        for c in ("E", "C"):   # 어서션 분류는 전역 테이블(code 유니크) — 테스트 간 공유
            cats[c] = db.query(BaselineRiskCategory).filter(BaselineRiskCategory.code == c).first()                 or BaselineRiskCategory(code=c, name=c)
            db.add(cats[c])
        p = BaselineProcess(code="XP", name="프로세스")
        db.add(p)
        db.flush()
        sp = BaselineSubProcess(code="XP-010", name="하위", process_id=p.id)
        db.add(sp)
        db.flush()
        r = BaselineRisk(code="XP-010-10", description="위험", assessment_level="LR", sub_process_id=sp.id)
        db.add(r)
        db.flush()
        c1 = BaselineControl(code="XP-010-10-10", name="통제1", risk_id=r.id, owner_name="갑", objective="목적",
                             description="설명", frequency="M", assessment_frequency="quarterly")
        c2 = BaselineControl(code="XP-010-10-20", name="통제2", risk_id=r.id, owner_name="을", frequency="A",
                             assessment_frequency="annual")
        db.add_all([c1, c2])
        db.flush()
        db.add(BaselineControlAssertion(baseline_control_id=c1.id, baseline_risk_category_id=cats["E"].id))
        db.commit()
    finally:
        reset_active_tenant(tok)
        db.close()


def _row(c_code, c_name, owner, *, freq="M", e=False, c=False, desc="설명", obj="목적"):
    row = [None] * 45
    row[1], row[2], row[3], row[4], row[5] = "XP", "프로세스", "XP-010", "하위", "XP-010-10"
    row[6], row[7], row[8], row[14] = c_code, owner, "위험", "LR"
    row[15], row[16], row[17], row[18] = obj, c_name, desc, "Yes"
    row[25], row[26], row[35], row[36] = "P", "M", freq, "N/A"
    row[27] = "O" if e else None
    row[28] = "O" if c else None
    return row


def _excel(rows) -> bytes:
    wb = Workbook()
    ws = wb.active
    for _ in range(6):
        ws.append([None] * 45)
    hdr = [None] * 45
    hdr[1], hdr[6], hdr[16] = "프로세스번호", "통제활동번호", "통제활동이름"
    ws.append(hdr)
    for r in rows:
        ws.append(r)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _post(client, t, rows, mode):
    return client.post(U, headers=t.h["master"], data={"mode": mode},
                       files={"file": ("rcm.xlsx", _excel(rows), XLSX)})


# 담당자 변경 + 어서션 C 추가(C1), 새 통제 1건, C2 는 엑셀에 없음
ROWS = [_row("XP-010-10-10", "통제1", "병", e=True, c=True), _row("XP-010-10-30", "새 통제", "정", freq="Q")]


def test_preview_shows_diff_against_live_and_missing(client: TestClient) -> None:
    t = T(client, {"master": ("icfr_manager",)})
    _seed(t)
    r = _post(client, t, ROWS, "preview")
    assert r.status_code == 200, r.text
    sync = r.json()["sync"]
    ctl = sync["diff"]["layers"]["controls"]
    assert [a["code"] for a in ctl["added"]] == ["XP-010-10-30"]
    assert ctl["removed"] == []           # 엑셀에 없는 C2 는 삭제로 계획하지 않는다(Q1)
    (ch,) = ctl["changed"]
    got = {f["field"]: (f["before"], f["after"]) for f in ch["changes"]}
    assert got == {"owner_name": ("갑", "병"), "assertions": ("E", "C, E")}   # 평가 주기는 엑셀에 없어 비교하지 않는다
    assert sync["missing"]["controls"] == ["XP-010-10-20"] and sync["missing_count"] == 1
    assert sync["summary_text"] == "통제 1건 변경·1건 추가"
    # 미리보기는 아무것도 바꾸지 않는다
    items = {c["code"]: c for c in client.get("/api/rcm/controls", headers=t.h["master"], params={"limit": 50}).json()["items"]}
    assert items["XP-010-10-10"]["owner_name"] == "갑" and "XP-010-10-30" not in items


def test_commit_applies_as_company_overlay(client: TestClient) -> None:
    t = T(client, {"master": ("icfr_manager",)})
    _seed(t)
    r = _post(client, t, ROWS, "commit")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"]["controls"] == 1 and body["updated"]["controls"] == 1
    assert body["summary_text"] == "통제 1건 변경·1건 추가" and body["missing_count"] == 1
    logs = client.get("/api/admin/audit-logs", headers=t.h["master"], params={"module": "RCM"}).json()["items"]
    assert logs[0]["action"] == "RCM 엑셀 업로드" and logs[0]["target_label"] == "통제 1건 변경·1건 추가"
    items = {c["code"]: c for c in client.get("/api/rcm/controls", headers=t.h["master"], params={"limit": 50}).json()["items"]}
    c1 = items["XP-010-10-10"]
    assert c1["owner_name"] == "병" and c1["assessment_frequency"] == "quarterly" and c1["source"] == "baseline"
    assert items["XP-010-10-20"]["owner_name"] == "을"          # 엑셀에 없어도 남는다
    assert items["XP-010-10-30"]["source"] == "tenant" and items["XP-010-10-30"]["frequency"] == "Q"
    s = client.get("/api/rcm/controls/search", headers=t.h["master"], params={"q": "XP-010-10"}).json()["items"]
    assert {c["code"]: c["assertions"] for c in s}["XP-010-10-10"] == ["C", "E"]
    # 기준 RCM 원본은 그대로 — 회사 수정분(override)만 생긴다
    db = TestingSessionLocal()
    tok = set_active_tenant(t.tid)
    try:
        assert db.query(BaselineControl).filter(BaselineControl.code == "XP-010-10-10").one().owner_name == "갑"
        assert db.query(ControlInstance).count() == 2   # override 1 + add 1
    finally:
        reset_active_tenant(tok)
        db.close()
    # 같은 파일을 다시 올리면 변경 없음
    again = _post(client, t, ROWS, "preview").json()["sync"]
    assert again["summary_text"] == "변경 없음" and again["op_count"] == 0


def test_locked_rcm_previews_but_refuses_commit(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})
    _seed(t)
    rid = client.post("/api/rcm-years", headers=t.h["lead"], json={"fiscal_year": 2026}).json()["id"]
    assert client.post(f"/api/rcm-years/{rid}/transition", headers=t.h["lead"], json={"to_status": "review"}).status_code == 200
    assert _post(client, t, ROWS, "preview").status_code == 200
    assert _post(client, t, ROWS, "commit").status_code == 409


def test_parent_change_is_warned_not_applied(client: TestClient) -> None:
    t = T(client, {"master": ("icfr_manager",)})
    _seed(t)
    row = _row("XP-010-10-10", "통제1", "갑", e=True)
    row[5] = "XP-010-20"         # 다른(새) 위험 밑으로
    sync = _post(client, t, [row], "preview").json()["sync"]
    assert any("XP-010-10-10" in w and "반영하지 않습니다" in w for w in sync["warnings"])
    assert [a["code"] for a in sync["diff"]["layers"]["risks"]["added"]] == ["XP-010-20"]
