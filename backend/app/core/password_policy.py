"""비밀번호 규칙 (보안 1단계, 2026-10-01) — 생성·관리자 재설정·본인 변경 세 경로가 같은 함수를 쓴다.

규칙: 10자 이상 + 영문·숫자·특수문자 모두 포함. 프론트 `features/auth/password.pure.ts` 와 같은 규칙이며,
판정의 진실은 여기다(프론트는 미리 알려줄 뿐). 기존 비밀번호에는 소급하지 않는다 — 로그인은 막지 않고,
다음 변경 때부터 적용된다.
"""
import re

MIN_LENGTH = 10


def password_problem(pw: str) -> str | None:
    """규칙 위반이면 사용자에게 보일 문구, 통과면 None."""
    if len(pw) < MIN_LENGTH:
        return f"비밀번호는 {MIN_LENGTH}자 이상이어야 합니다"
    missing = [name for name, pat in (("영문", r"[A-Za-z]"), ("숫자", r"\d"), ("특수문자", r"[^A-Za-z0-9\s]"))
               if not re.search(pat, pw)]
    if missing:
        return f"비밀번호에 {'·'.join(missing)}를 포함하세요 (영문·숫자·특수문자 모두 필요)"
    return None


def validate_password(pw: str) -> str:
    """pydantic field_validator 용 — 위반이면 ValueError(→ 422)."""
    problem = password_problem(pw)
    if problem:
        raise ValueError(problem)
    return pw
