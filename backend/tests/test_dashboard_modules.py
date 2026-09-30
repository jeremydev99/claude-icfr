"""대시보드 모듈 현황 — 메뉴 경로별 데이터 건수 (2026-09-30). 배지가 고정값이라 데이터가 있어도 "데이터 없음"이던 문제."""
import pytest
from fastapi.testclient import TestClient

from seeds.seed_scoping_template import load_template
from tests.conftest import TestingSessionLocal
from tests.test_fs_upload import _post, _tenant, bs_wb


@pytest.fixture(scope="module", autouse=True)
def template(app):
    db = TestingSessionLocal()
    try:
        _, _, created = load_template(db)
        if created:
            db.commit()
    finally:
        db.close()


def test_module_counts_follow_data_and_tenant(client: TestClient) -> None:
    h, _ = _tenant(client)
    before = client.get("/api/dashboard/modules", headers=h)
    assert before.status_code == 200, before.text
    b = before.json()
    assert b["/financial-statements"] == 0 and b["/scoping"] == 0 and b["/users"] == 1
    assert {"/rcm", "/euc", "/iuc", "/test", "/remediation", "/evidence", "/schedule", "/admin/departments",
            "/admin/role-assignments", "/admin/policies", "/admin/fiscal-year"} <= set(b)
    assert _post(client, h, bs_wb(), mode="commit").status_code == 200
    assert client.post("/api/scoping", headers=h, json={"fiscal_year": 2026}).status_code == 201
    a = client.get("/api/dashboard/modules", headers=h).json()
    assert a["/financial-statements"] == 1 and a["/scoping"] == 1
    other, _ = _tenant(client)                                                     # 다른 테넌트에는 안 보인다
    assert client.get("/api/dashboard/modules", headers=other).json()["/financial-statements"] == 0
