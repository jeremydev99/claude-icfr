"""비밀번호 규칙 — 생성·관리자 재설정·본인 변경 세 경로가 같은 함수를 쓴다.

현재 규칙: **8자 이상**. 보안 1단계(2026-10-01)에 10자 + 영문·숫자·특수문자로 올렸다가, 마스터 지시
("아직은 출시 전이니 기존 8자로")로 같은 날 되돌렸다. 강화할 때는 여기와 프론트 `features/auth/password.pure.ts`
를 함께 고친다 — 판정의 진실은 여기다(프론트는 미리 알려줄 뿐).
"""
MIN_LENGTH = 8


def password_problem(pw: str) -> str | None:
    """규칙 위반이면 사용자에게 보일 문구, 통과면 None."""
    if len(pw) < MIN_LENGTH:
        return f"비밀번호는 {MIN_LENGTH}자 이상이어야 합니다"
    return None


def validate_password(pw: str) -> str:
    """pydantic field_validator 용 — 위반이면 ValueError(→ 422)."""
    problem = password_problem(pw)
    if problem:
        raise ValueError(problem)
    return pw
