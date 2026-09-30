

def test_login_email_is_case_and_space_insensitive(client) -> None:
    """휴대폰 키보드가 첫 글자를 대문자로 바꾸거나 공백을 붙여도 로그인된다(2026-09-30)."""
    for username in ("Admin@Acme.Example", "  admin@acme.example ", "ADMIN@ACME.EXAMPLE"):
        r = client.post("/api/auth/login", data={"username": username, "password": "admin123"})
        assert r.status_code == 200, (username, r.text)
    assert client.post("/api/auth/login", data={"username": "Admin@Acme.Example", "password": "wrong"}).status_code == 401
