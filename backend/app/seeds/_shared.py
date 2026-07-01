import httpx

from app.core.tenant_context import DEFAULT_TENANT_ID


class SeedContext:
    """시드 실행 컨텍스트 — HTTP 클라이언트, 인증 토큰, 공유 ID 레지스트리."""

    def __init__(self, base_url: str = "http://localhost:8000", tenant_id: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None
        self.tenant_id: str = tenant_id or str(DEFAULT_TENANT_ID)
        self.ids: dict = {}

    def login(self, email: str, password: str) -> None:
        resp = httpx.post(
            f"{self.base_url}/api/auth/login",
            data={"username": email, "password": password},
        )
        resp.raise_for_status()
        self.token = resp.json()["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "X-Tenant-Id": self.tenant_id}

    def get(self, path: str, params: dict | None = None) -> dict:
        resp = httpx.get(f"{self.base_url}{path}", headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, json: dict) -> dict:
        resp = httpx.post(f"{self.base_url}{path}", headers=self._headers(), json=json)
        resp.raise_for_status()
        return resp.json()


def get_or_create(ctx: SeedContext, list_path: str, create_path: str, lookup_key: str, lookup_value: str, payload: dict) -> dict:
    """기존 항목이 있으면 반환, 없으면 생성. 멱등성 보장."""
    data = ctx.get(list_path)
    for item in data.get("items", []):
        if item.get(lookup_key) == lookup_value:
            print(f"  [{list_path}] {lookup_key}={lookup_value} exists (skip)")
            return item
    obj = ctx.post(create_path, payload)
    print(f"  [{list_path}] {lookup_key}={lookup_value} created")
    return obj
