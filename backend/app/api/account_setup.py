"""직원 계정 설정 링크 — 공개 경로(로그인 전). 직원이 링크에서 비밀번호를 직접 정한다(ADR-0041)."""
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.audit_context import system_actor
from app.core.database import get_db
from app.core.password_policy import validate_password
from app.services import account_setup as svc

public = APIRouter(prefix="/api/account-setup", tags=["account_setup"])


class SetupInfo(BaseModel):
    email: str
    display_name: str
    purpose: str          # invite | reset
    expires_at: datetime


class SetupBody(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def _strong(cls, v: str) -> str:
        return validate_password(v)


@public.get("/{token}", response_model=SetupInfo)
def setup_info(token: str, db: Session = Depends(get_db)) -> SetupInfo:
    t, u = svc.by_token(db, token)
    return SetupInfo(email=u.email, display_name=u.display_name, purpose=t.purpose, expires_at=t.expires_at)


@public.post("/{token}")
def setup_complete(token: str, body: SetupBody, request: Request, db: Session = Depends(get_db)) -> dict:
    with system_actor("system:account-setup"):
        u = svc.complete(db, token, body.password)
        request.state.audit_user_id = u.id   # 감사 로그 — 토큰 없는 요청이라 계정을 직접 알린다
        db.commit()
    return {"detail": "비밀번호를 설정했습니다 — 로그인하세요", "email": u.email}
