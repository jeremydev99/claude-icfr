"""RCM 모듈 통합 테스트 — Phase 1 풀 확장."""
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook


def _token(client: TestClient) -> str:
    resp = client.post("/api/auth/login", data={"username": "admin@acme.example", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _headers(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {_token(client)}"}


def _make_test_excel(
    p_code="TP", p_name="테스트프로세스",
    sp_code="TP-010", sp_name="테스트하위",
    r_code="TP-010-10",
    c_code="TP-010-10-10", c_name="테스트통제",
) -> bytes:
    """최소 RCM Excel 파일 생성 (테스트용)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "RCM"
    for _ in range(7):
        ws.append([None] * 45)
    row = [None] * 45
    row[1] = p_code    # B
    row[2] = p_name    # C
    row[3] = sp_code   # D
    row[4] = sp_name   # E
    row[5] = r_code    # F
    row[6] = c_code    # G
    row[7] = "관리자"   # H
    row[8] = "테스트위험"  # I
    row[14] = "LR"     # O
    row[15] = "통제목적"  # P
    row[16] = c_name   # Q
    row[17] = "통제설명"  # R
    row[18] = "Yes"    # S
    row[19] = "O"      # T
    row[25] = "P"      # Z
    row[26] = "M"      # AA
    row[27] = "O"      # AB — assertion E
    row[28] = "O"      # AC — assertion C
    row[35] = "M"      # AJ
    row[36] = "N/A"    # AK
    ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── Process CRUD ──────────────────────────────────────────

def test_process_crud(client: TestClient) -> None:
    h = _headers(client)
    resp = client.post("/api/rcm/processes", json={"code": "P-TEST", "name": "테스트 프로세스"}, headers=h)
    assert resp.status_code == 201
    pid = resp.json()["id"]

    resp = client.get(f"/api/rcm/processes/{pid}", headers=h)
    assert resp.status_code == 200

    resp = client.get("/api/rcm/processes", headers=h)
    assert resp.json()["total"] >= 1

    resp = client.patch(f"/api/rcm/processes/{pid}", json={"name": "수정된 프로세스"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["name"] == "수정된 프로세스"

    resp = client.delete(f"/api/rcm/processes/{pid}", headers=h)
    assert resp.status_code == 204

    resp = client.get(f"/api/rcm/processes/{pid}", headers=h)
    assert resp.status_code == 404


# ── SubProcess CRUD ───────────────────────────────────────

def test_subprocess_crud(client: TestClient) -> None:
    h = _headers(client)
    p = client.post("/api/rcm/processes", json={"code": "P-SP-TEST", "name": "SP 테스트 프로세스"}, headers=h)
    pid = p.json()["id"]

    resp = client.post("/api/rcm/sub-processes", json={"code": "SP-010", "name": "하위프로세스", "process_id": pid}, headers=h)
    assert resp.status_code == 201
    sp_id = resp.json()["id"]
    assert resp.json()["code"] == "SP-010"

    resp = client.get(f"/api/rcm/sub-processes/{sp_id}", headers=h)
    assert resp.status_code == 200

    resp = client.get("/api/rcm/sub-processes", headers=h)
    assert resp.json()["total"] >= 1

    resp = client.patch(f"/api/rcm/sub-processes/{sp_id}", json={"name": "수정된 하위프로세스"}, headers=h)
    assert resp.status_code == 200

    resp = client.delete(f"/api/rcm/sub-processes/{sp_id}", headers=h)
    assert resp.status_code == 204


# ── Risk CRUD ─────────────────────────────────────────────

def test_risk_crud(client: TestClient) -> None:
    h = _headers(client)
    p = client.post("/api/rcm/processes", json={"code": "P-RISK-TEST", "name": "Risk 테스트"}, headers=h)
    sp = client.post("/api/rcm/sub-processes", json={"code": "SP-RISK-010", "name": "SP", "process_id": p.json()["id"]}, headers=h)

    resp = client.post("/api/rcm/risks", json={
        "code": "RISK-010-10",
        "description": "테스트 위험",
        "assessment_level": "MR",
        "sub_process_id": sp.json()["id"],
    }, headers=h)
    assert resp.status_code == 201
    risk_id = resp.json()["id"]
    assert resp.json()["assessment_level"] == "MR"

    resp = client.get(f"/api/rcm/risks/{risk_id}", headers=h)
    assert resp.status_code == 200

    resp = client.patch(f"/api/rcm/risks/{risk_id}", json={"assessment_level": "HR"}, headers=h)
    assert resp.json()["assessment_level"] == "HR"

    resp = client.delete(f"/api/rcm/risks/{risk_id}", headers=h)
    assert resp.status_code == 204


# ── Control CRUD (새 구조) ─────────────────────────────────

def test_control_extended_crud(client: TestClient) -> None:
    h = _headers(client)
    p = client.post("/api/rcm/processes", json={"code": "P-CTL-EXT", "name": "통제 테스트"}, headers=h)
    sp = client.post("/api/rcm/sub-processes", json={"code": "SP-CTL-010", "name": "SP", "process_id": p.json()["id"]}, headers=h)
    r = client.post("/api/rcm/risks", json={
        "code": "CTL-RISK-010", "description": "위험", "assessment_level": "LR", "sub_process_id": sp.json()["id"]
    }, headers=h)
    risk_id = r.json()["id"]

    resp = client.post("/api/rcm/controls", json={
        "code": "CTL-EXT-001",
        "name": "확장 통제",
        "risk_id": risk_id,
        "frequency": "M",
        "is_key_control": True,
        "preventive_detective": "P",
        "auto_manual": "M",
        "activity_approval": True,
        "ipe_relevant": "N/A",
    }, headers=h)
    assert resp.status_code == 201
    cid = resp.json()["id"]
    assert resp.json()["frequency"] == "M"
    assert resp.json()["activity_approval"] is True

    resp = client.get(f"/api/rcm/controls/{cid}", headers=h)
    assert resp.status_code == 200

    resp = client.patch(f"/api/rcm/controls/{cid}", json={"frequency": "Q", "auto_manual": "A"}, headers=h)
    assert resp.json()["frequency"] == "Q"
    assert resp.json()["auto_manual"] == "A"

    resp = client.get("/api/rcm/controls", headers=h)
    assert resp.json()["total"] >= 1

    resp = client.delete(f"/api/rcm/controls/{cid}", headers=h)
    assert resp.status_code == 204


# ── Excel 업로드 ──────────────────────────────────────────

def test_excel_upload_preview(client: TestClient) -> None:
    h = _headers(client)
    excel = _make_test_excel()
    resp = client.post(
        "/api/rcm/upload-excel",
        files={"file": ("test_rcm.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"mode": "preview"},
        headers=h,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert data["summary"]["valid_rows"] == 1
    assert len(data["preview"]) == 1
    assert data["preview"][0]["code"] == "TP-010-10-10"


def test_excel_upload_commit(client: TestClient) -> None:
    h = _headers(client)
    excel = _make_test_excel(
        p_code="EC-P", sp_code="EC-P-010", r_code="EC-P-010-10",
        c_code="EC-P-010-10-10", c_name="Excel Commit 통제"
    )
    resp = client.post(
        "/api/rcm/upload-excel",
        files={"file": ("test_rcm.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"mode": "commit"},
        headers=h,
    )
    assert resp.status_code == 200
    created = resp.json()["created"]
    assert created["controls"] == 1
    assert created["assertions"] >= 1

    # 실제로 DB에 저장됐는지 확인
    resp = client.get("/api/rcm/controls", headers=h, params={"limit": 200})
    codes = [c["code"] for c in resp.json()["items"]]
    assert "EC-P-010-10-10" in codes


# ── 검색 API ──────────────────────────────────────────────

def test_search_text(client: TestClient) -> None:
    h = _headers(client)
    # 검색 전 통제 생성
    p = client.post("/api/rcm/processes", json={"code": "SRCH-P", "name": "검색 프로세스"}, headers=h)
    sp = client.post("/api/rcm/sub-processes", json={"code": "SRCH-SP", "name": "검색 SP", "process_id": p.json()["id"]}, headers=h)
    r = client.post("/api/rcm/risks", json={"code": "SRCH-R", "description": "위험", "assessment_level": "LR", "sub_process_id": sp.json()["id"]}, headers=h)
    client.post("/api/rcm/controls", json={"code": "SRCH-CTL-001", "name": "검색용통제명칭", "risk_id": r.json()["id"], "frequency": "M"}, headers=h)

    resp = client.get("/api/rcm/controls/search", params={"q": "검색용통제"}, headers=h)
    assert resp.status_code == 200
    codes = [c["code"] for c in resp.json()["items"]]
    assert "SRCH-CTL-001" in codes


def test_search_filter_combination(client: TestClient) -> None:
    h = _headers(client)
    resp = client.get("/api/rcm/controls/search", params={"frequency": "M", "is_key_control": "true"}, headers=h)
    assert resp.status_code == 200
    assert "total" in resp.json()


# ── 매트릭스 API ──────────────────────────────────────────

def test_matrix_endpoint(client: TestClient) -> None:
    h = _headers(client)
    resp = client.get("/api/rcm/matrix", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert "matrix" in data
    assert "summary" in data
    assert "process_count" in data["summary"]


# ── 벌크 작업 ─────────────────────────────────────────────

def test_bulk_delete(client: TestClient) -> None:
    h = _headers(client)
    p = client.post("/api/rcm/processes", json={"code": "BLK-P", "name": "벌크 삭제 테스트"}, headers=h)
    sp = client.post("/api/rcm/sub-processes", json={"code": "BLK-SP", "name": "SP", "process_id": p.json()["id"]}, headers=h)
    r = client.post("/api/rcm/risks", json={"code": "BLK-R", "description": "위험", "assessment_level": "LR", "sub_process_id": sp.json()["id"]}, headers=h)
    c1 = client.post("/api/rcm/controls", json={"code": "BLK-C-001", "name": "벌크1", "risk_id": r.json()["id"], "frequency": "A"}, headers=h)
    c2 = client.post("/api/rcm/controls", json={"code": "BLK-C-002", "name": "벌크2", "risk_id": r.json()["id"], "frequency": "A"}, headers=h)

    resp = client.post("/api/rcm/controls/bulk-delete", json={"control_ids": [c1.json()["id"], c2.json()["id"]]}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["deleted_count"] == 2


def test_clear_all(client: TestClient) -> None:
    h = _headers(client)
    # clear-all 이후 controls가 0이어야 함
    resp = client.post("/api/rcm/controls/clear-all", json={"confirm": "DELETE_ALL_RCM_DATA"}, headers=h)
    assert resp.status_code == 200
    deleted = resp.json()["deleted"]
    assert "controls" in deleted

    resp = client.get("/api/rcm/controls", headers=h)
    assert resp.json()["total"] == 0
