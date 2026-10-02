"""RCM 쓰기 가드 — 13.9-77. 평가 영역 가드(`test_eval_write_guard.py`, 13.9-76)와 같은 방식.

`external_auditor` 는 조회 전용이다(ADR-0031 §2.1). RCM 쓰기 20개가 `CurrentUser` 만 받아
외부감사인이 통제·상위 계층·어서션을 고치고 엑셀로 일괄 반영할 수 있었다.

엑셀 업로드는 `mode=preview` 도 막는다 — 외부감사인이 쓸 일이 없고, 한 엔드포인트가
미리보기·저장을 겸하므로 모드별로 가드를 나누면 판정이 두 곳이 된다.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.test_eval_write_guard import _external_auditor_headers

_ID = str(uuid4())

WRITE_ROUTES = [
    ("POST", "/api/rcm/processes"),
    ("PATCH", f"/api/rcm/processes/{_ID}"),
    ("DELETE", f"/api/rcm/processes/{_ID}"),
    ("POST", "/api/rcm/sub-processes"),
    ("PATCH", f"/api/rcm/sub-processes/{_ID}"),
    ("DELETE", f"/api/rcm/sub-processes/{_ID}"),
    ("POST", "/api/rcm/risks"),
    ("PATCH", f"/api/rcm/risks/{_ID}"),
    ("DELETE", f"/api/rcm/risks/{_ID}"),
    ("POST", "/api/rcm/risk-categories"),
    ("PATCH", f"/api/rcm/risk-categories/{_ID}"),
    ("DELETE", f"/api/rcm/risk-categories/{_ID}"),
    ("POST", "/api/rcm/controls/bulk-delete"),
    ("POST", "/api/rcm/controls/bulk-update"),
    ("POST", "/api/rcm/controls"),
    ("PATCH", f"/api/rcm/controls/{_ID}"),
    ("DELETE", f"/api/rcm/controls/{_ID}"),
    ("POST", "/api/rcm/control-assertions"),
    ("DELETE", f"/api/rcm/control-assertions/{_ID}"),
    ("POST", "/api/rcm/upload-excel"),
]


@pytest.mark.parametrize(("method", "path"), WRITE_ROUTES)
def test_external_auditor_cannot_write(client: TestClient, method: str, path: str) -> None:
    h = _external_auditor_headers(client)
    kwargs = {} if method == "DELETE" or path.endswith("upload-excel") else {"json": {}}
    resp = client.request(method, path, headers=h, **kwargs)
    assert resp.status_code == 403, f"{method} {path} → {resp.status_code} {resp.text}"
    assert "외부감사인" in resp.json()["detail"]


def test_external_auditor_can_still_read(client: TestClient) -> None:
    h = _external_auditor_headers(client)
    for path in ("/api/rcm/controls", "/api/rcm/processes", "/api/rcm/sub-processes",
                 "/api/rcm/risks", "/api/rcm/risk-categories"):
        assert client.get(path, headers=h).status_code == 200, path


def test_every_write_route_is_listed() -> None:
    """rcm 라우터의 쓰기 엔드포인트가 전부 WRITE_ROUTES 에 있다 — 새 쓰기 경로의 가드 누락 방지."""
    from app.api import rcm

    listed = {(m, p.replace(_ID, "{id}")) for m, p in WRITE_ROUTES}
    actual = set()
    for r in rcm.router.routes:
        for m in r.methods - {"GET", "HEAD", "OPTIONS"}:
            path = r.path
            for name in ("process_id", "sp_id", "risk_id", "rc_id", "control_id", "ca_id"):
                path = path.replace("{" + name + "}", "{id}")
            actual.add((m, path))
    assert actual == listed, f"누락: {actual - listed} / 초과: {listed - actual}"
