"""RCM 바로 반영은 내부회계관리자만 (2026-10-08) — 통제 생성·삭제·상위 계층·어서션·엑셀 저장.

통제 필드 수정은 13.9-95 부터 이미 같은 기준이었다. 그 외 경로가 `require_write`(쓰기 권한자 누구나)로 남아
결재 없이 통제가 지워질 수 있었다.
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from tests.test_governance import T
from tests.test_rcm_approval import _control


def test_every_rcm_write_route_requires_direct_edit() -> None:
    """`/api/rcm/*` 쓰기 경로는 전부 `require_direct_control_edit` 를 거친다(엑셀은 저장 시 함수 안에서)."""
    from app.api.rcm import require_direct_control_edit
    from app.main import app

    def calls(dep):
        out = [dep.call]
        for d in dep.dependencies:
            out += calls(d)
        return out
    missing = []
    for r in app.routes:
        path = getattr(r, "path", "")
        if not path.startswith("/api/rcm/") or path.endswith("/upload-excel"):
            continue
        for m in (getattr(r, "methods", None) or ()):
            if m in ("POST", "PUT", "PATCH", "DELETE") and require_direct_control_edit not in calls(r.dependant):
                missing.append(f"{m} {path}")
    assert missing == []


def test_non_master_writer_gets_403_master_passes(client: TestClient) -> None:
    t = T(client, {"master": ("icfr_manager",), "staff": ("icfr_staff",), "owner": ()})
    cid = _control(t)
    code = f"DE{uuid4().hex[:4]}"
    for who in ("staff", "owner"):
        r = client.post("/api/rcm/processes", headers=t.h[who], json={"code": code, "name": "새 프로세스"})
        assert r.status_code == 403 and "내부회계관리자" in r.json()["detail"], r.text
        assert client.delete(f"/api/rcm/controls/{cid}", headers=t.h[who]).status_code == 403
        assert client.post("/api/rcm/controls/bulk-delete", headers=t.h[who], json={"ids": [cid]}).status_code == 403
    assert client.post("/api/rcm/processes", headers=t.h["master"], json={"code": code, "name": "새 프로세스"}).status_code == 201
    assert client.delete(f"/api/rcm/controls/{cid}", headers=t.h["master"]).status_code == 204


def test_company_without_master_keeps_old_behavior(client: TestClient) -> None:
    """내부회계관리자가 아직 없는 회사는 결재할 사람이 없으므로 종전처럼 쓰기 권한자가 반영한다."""
    t = T(client, {"owner": ()})
    _control(t)
    r = client.post("/api/rcm/processes", headers=t.h["owner"], json={"code": f"NM{uuid4().hex[:4]}", "name": "P"})
    assert r.status_code == 201, r.text
