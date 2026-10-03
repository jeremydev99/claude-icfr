"""외부 사용자 — 초대(요청·승인·취소), 수락(공개), 접근 범위(연장·해지), 정기 재확인 (ADR-0039).

- 초대 요청: 책임·마스터관리자. 승인: 마스터관리자, **요청자 본인 불가**(ADR-0038 자기 승인 금지).
- 승인 시 1회용 토큰을 만들어 **링크를 한 번만** 돌려준다(토큰은 SHA-256 해시만 저장, 72시간).
- 수락은 로그인 없이(공개). 같은 이메일 계정이 있으면 그 비밀번호를 확인해 연결하고, 없으면 만든다.
  수락 후 MFA 등록(외부는 필수)으로 이어진다 — 수락 응답이 `mfa_token`(setup)을 준다.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import governance_log as glog
from app.core.audit_context import system_actor
from app.core.database import get_db
from app.core.deps import CurrentUser, require_admin
from app.core.password_policy import validate_password
from app.core.security import create_mfa_token, hash_password, verify_password
from app.core.tenant_context import reset_active_tenant, set_active_tenant
from app.models.external import (
    DEFAULT_MODULES,
    EXT_ACTIVE,
    EXT_REVOKED,
    INV_ACCEPTED,
    INV_APPROVED,
    INV_EXPIRED,
    INV_LABELS,
    INV_PENDING,
    INV_REVOKED,
    TYPE_LABELS,
    TYPE_ROLE,
    AccessReview,
    ExternalProfile,
    Invitation,
)
from app.models.tenant import Tenant, UserTenantAccess
from app.models.user import User
from app.models.user_mgmt import UserRole
from app.services import approval

router = APIRouter(prefix="/api/external", tags=["external"])
public = APIRouter(prefix="/api/invite", tags=["external"])
ENTITY = "external_access"
TOKEN_HOURS = 72


def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _name(db: Session, uid) -> str | None:
    if uid is None:
        return None
    u = db.get(User, uid)
    return u.display_name if u else None


def _need_tier(db: Session, user: User, min_tier: int, what: str) -> None:
    if approval.user_tier(db, user.id) < min_tier:
        raise HTTPException(status_code=403, detail=f"{what}은(는) {'마스터' if min_tier == 3 else '책임·마스터'}관리자만 합니다")


# ── 스키마 ──
class InviteCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=100)
    user_type: str = Field(pattern="^(advisor|auditor|committee|specialist)$")
    organization: str = Field(min_length=1, max_length=200)
    modules: list[str] | None = None
    valid_from: date | None = None
    valid_until: date
    note: str | None = None


class InviteOut(BaseModel):
    id: UUID
    email: str
    display_name: str
    user_type: str
    type_label: str
    organization: str
    modules: list[str] | None
    valid_from: date
    valid_until: date
    note: str | None
    status: str
    status_label: str
    requested_by: str | None
    approved_by: str | None
    token_expires_at: datetime | None
    accepted_at: datetime | None
    created_at: datetime
    invite_url: str | None = None   # 승인 직후 응답에만 — 다시 볼 수 없다


class ProfileOut(BaseModel):
    id: UUID
    user_id: UUID
    email: str
    display_name: str
    user_type: str
    type_label: str
    organization: str
    modules: list[str] | None
    valid_from: date
    valid_until: date
    status: str
    mfa_enabled: bool
    last_login_at: datetime | None
    last_reviewed_at: datetime | None
    last_reviewed_by: str | None


class ProfileUpdate(BaseModel):
    valid_until: date | None = None
    modules: list[str] | None = None


class Reason(BaseModel):
    reason: str | None = None


def _inv_out(db: Session, i: Invitation, url: str | None = None) -> InviteOut:
    return InviteOut(id=i.id, email=i.email, display_name=i.display_name, user_type=i.user_type,
                     type_label=TYPE_LABELS.get(i.user_type, i.user_type), organization=i.organization, modules=i.modules,
                     valid_from=i.valid_from, valid_until=i.valid_until, note=i.note, status=i.status,
                     status_label=INV_LABELS.get(i.status, i.status), requested_by=_name(db, i.requested_by_id),
                     approved_by=_name(db, i.approved_by_id), token_expires_at=i.token_expires_at,
                     accepted_at=i.accepted_at, created_at=i.created_at, invite_url=url)


def _expire_stale(db: Session) -> None:
    now = datetime.now(UTC)
    for i in db.query(Invitation).filter(Invitation.status == INV_APPROVED, Invitation.is_deleted == False).all():  # noqa: E712
        exp = i.token_expires_at if i.token_expires_at.tzinfo else i.token_expires_at.replace(tzinfo=UTC)
        if exp < now:
            i.status = INV_EXPIRED


# ── 초대 ──
@router.get("/invitations", response_model=list[InviteOut])
def list_invitations(user: CurrentUser, db: Session = Depends(get_db)) -> list[InviteOut]:
    _need_tier(db, user, 2, "외부 사용자 관리")
    _expire_stale(db)
    db.commit()
    rows = db.query(Invitation).filter(Invitation.is_deleted == False).order_by(Invitation.created_at.desc()).limit(200).all()  # noqa: E712
    return [_inv_out(db, i) for i in rows]


@router.post("/invitations", response_model=InviteOut, status_code=201)
def create_invitation(body: InviteCreate, user: CurrentUser, db: Session = Depends(get_db)) -> InviteOut:
    _need_tier(db, user, 2, "초대 요청")
    start = body.valid_from or date.today()
    if body.valid_until < start:
        raise HTTPException(status_code=422, detail="종료일이 시작일보다 빠릅니다")
    modules = body.modules if body.modules is not None else DEFAULT_MODULES.get(body.user_type)
    i = Invitation(email=str(body.email).strip().lower(), display_name=body.display_name.strip(),
                   user_type=body.user_type, organization=body.organization.strip(), modules=modules,
                   valid_from=start, valid_until=body.valid_until, note=(body.note or "").strip() or None,
                   status=INV_PENDING, requested_by_id=user.id)
    db.add(i)
    db.flush()
    glog.record(db, i.id, "invite_request", version=None, entity_type=ENTITY, target=f"{i.organization} {i.display_name}",
                after={"이메일": i.email, "유형": TYPE_LABELS[i.user_type], "기간": f"{start}~{body.valid_until}",
                       "모듈": modules})
    db.commit()
    return _inv_out(db, i)


@router.post("/invitations/{iid}/approve", response_model=InviteOut)
def approve_invitation(iid: UUID, request: Request, user: CurrentUser, db: Session = Depends(get_db)) -> InviteOut:
    _need_tier(db, user, 3, "초대 승인")
    i = db.query(Invitation).filter(Invitation.id == iid, Invitation.is_deleted == False).first()  # noqa: E712
    if i is None:
        raise HTTPException(status_code=404, detail="초대를 찾을 수 없습니다")
    if i.status != INV_PENDING:
        raise HTTPException(status_code=409, detail=f"승인할 수 없는 상태입니다({INV_LABELS.get(i.status)})")
    if i.requested_by_id == user.id:
        raise HTTPException(status_code=409, detail="초대 요청자는 본인 요청을 승인할 수 없습니다 — 자기 승인 금지")
    token = secrets.token_urlsafe(32)
    i.token_hash, i.token_expires_at = _h(token), datetime.now(UTC) + timedelta(hours=TOKEN_HOURS)
    i.status, i.approved_by_id, i.approved_at = INV_APPROVED, user.id, datetime.now(UTC)
    glog.record(db, i.id, "invite_approve", version=None, entity_type=ENTITY, target=f"{i.organization} {i.display_name}",
                after={"링크 만료": i.token_expires_at.isoformat()})
    db.commit()
    origin = request.headers.get("origin") or f"{request.url.scheme}://{request.headers.get('host', '')}"
    return _inv_out(db, i, url=f"{origin}/invite/{token}")


@router.post("/invitations/{iid}/revoke", response_model=InviteOut)
def revoke_invitation(iid: UUID, body: Reason, user: CurrentUser, db: Session = Depends(get_db)) -> InviteOut:
    _need_tier(db, user, 2, "초대 취소")
    i = db.query(Invitation).filter(Invitation.id == iid, Invitation.is_deleted == False).first()  # noqa: E712
    if i is None:
        raise HTTPException(status_code=404, detail="초대를 찾을 수 없습니다")
    if i.status not in (INV_PENDING, INV_APPROVED):
        raise HTTPException(status_code=409, detail="이미 끝난 초대입니다")
    i.status, i.token_hash, i.closed_reason = INV_REVOKED, None, (body.reason or "").strip() or None
    glog.record(db, i.id, "invite_revoke", version=None, entity_type=ENTITY, reason=i.closed_reason,
                target=f"{i.organization} {i.display_name}")
    db.commit()
    return _inv_out(db, i)


# ── 수락(공개) ──
class InvitePublic(BaseModel):
    email: str
    display_name: str
    organization: str
    type_label: str
    company: str
    valid_from: date
    valid_until: date
    existing_account: bool


class AcceptBody(BaseModel):
    password: str
    confidentiality: bool


class AcceptOut(BaseModel):
    mfa_token: str | None = None       # 이어서 MFA 등록(외부 필수)
    mfa_required: bool = False         # 이미 MFA 가 있는 기존 계정 — 로그인 화면으로


def _by_token(db: Session, token: str) -> Invitation:
    i = db.query(Invitation).filter(Invitation.token_hash == _h(token), Invitation.is_deleted == False).first()  # noqa: E712
    if i is None or i.status != INV_APPROVED:
        raise HTTPException(status_code=404, detail="유효하지 않은 초대 링크입니다")
    exp = i.token_expires_at if i.token_expires_at.tzinfo else i.token_expires_at.replace(tzinfo=UTC)
    if exp < datetime.now(UTC):
        raise HTTPException(status_code=410, detail="초대 링크가 만료됐습니다 — 담당자에게 다시 요청하세요")
    return i


@public.get("/{token}", response_model=InvitePublic)
def invite_info(token: str, db: Session = Depends(get_db)) -> InvitePublic:
    i = _by_token(db, token)
    t = db.get(Tenant, i.tenant_id)
    exists = db.query(User).filter(func.lower(User.email) == i.email, User.is_deleted == False).first() is not None  # noqa: E712
    return InvitePublic(email=i.email, display_name=i.display_name, organization=i.organization,
                        type_label=TYPE_LABELS[i.user_type], company=t.name if t else "", valid_from=i.valid_from,
                        valid_until=i.valid_until, existing_account=exists)


@public.post("/{token}/accept", response_model=AcceptOut)
def invite_accept(token: str, body: AcceptBody, db: Session = Depends(get_db)) -> AcceptOut:
    i = _by_token(db, token)
    if not body.confidentiality:
        raise HTTPException(status_code=422, detail="비밀유지 의무에 동의해야 합니다")
    tok = set_active_tenant(i.tenant_id)
    try:
        with system_actor("system:invite-accept"):
            u = db.query(User).filter(func.lower(User.email) == i.email, User.is_deleted == False).first()  # noqa: E712
            if u is not None:
                if not verify_password(body.password, u.hashed_password):
                    raise HTTPException(status_code=401, detail="기존 계정의 비밀번호가 올바르지 않습니다")
            else:
                try:
                    validate_password(body.password)
                except ValueError as e:
                    raise HTTPException(status_code=422, detail=str(e)) from None
                u = User(email=i.email, hashed_password=hash_password(body.password), display_name=i.display_name,
                         role="user", is_active=True)
                db.add(u)
                db.flush()
            if db.query(UserTenantAccess).filter(UserTenantAccess.user_id == u.id, UserTenantAccess.tenant_id == i.tenant_id,
                                                 UserTenantAccess.is_deleted == False).first() is None:  # noqa: E712
                db.add(UserTenantAccess(user_id=u.id, tenant_id=i.tenant_id, role="user"))
            role = TYPE_ROLE[i.user_type]
            if db.query(UserRole).filter(UserRole.user_id == u.id, UserRole.role_name == role,
                                         UserRole.is_deleted == False).first() is None:  # noqa: E712
                db.add(UserRole(user_id=u.id, role_name=role))
            prof = db.query(ExternalProfile).filter(ExternalProfile.user_id == u.id,
                                                    ExternalProfile.is_deleted == False).first()  # noqa: E712
            if prof is None:
                prof = ExternalProfile(user_id=u.id)
                db.add(prof)
            prof.user_type, prof.organization, prof.modules = i.user_type, i.organization, i.modules
            prof.valid_from, prof.valid_until, prof.status = i.valid_from, i.valid_until, EXT_ACTIVE
            prof.invitation_id, prof.approved_by_id, prof.closed_reason = i.id, i.approved_by_id, None
            now = datetime.now(UTC)
            i.status, i.token_hash, i.accepted_user_id, i.accepted_at, i.confidentiality_at = INV_ACCEPTED, None, u.id, now, now
            glog.record(db, i.id, "invite_accept", version=None, entity_type=ENTITY, target=f"{i.organization} {i.display_name}",
                        after={"비밀유지 동의": now.isoformat()})
            db.commit()
            if u.mfa_enabled_at is not None:
                return AcceptOut(mfa_required=True)
            return AcceptOut(mfa_token=create_mfa_token(str(u.id), "setup"))
    finally:
        reset_active_tenant(tok)


# ── 외부 사용자(접근 범위) ──
def _profile_out(db: Session, p: ExternalProfile) -> ProfileOut:
    from app.models.login_event import LoginEvent
    u = db.get(User, p.user_id)
    last = db.query(func.max(LoginEvent.created_at)).filter(LoginEvent.user_id == p.user_id,
                                                            LoginEvent.reason.in_(["ok", "ok_recovery", "mfa_enrolled"])).scalar()
    return ProfileOut(id=p.id, user_id=p.user_id, email=u.email if u else "", display_name=u.display_name if u else "",
                      user_type=p.user_type, type_label=TYPE_LABELS.get(p.user_type, p.user_type), organization=p.organization,
                      modules=p.modules, valid_from=p.valid_from, valid_until=p.valid_until, status=p.status,
                      mfa_enabled=bool(u and u.mfa_enabled_at), last_login_at=last, last_reviewed_at=p.last_reviewed_at,
                      last_reviewed_by=_name(db, p.last_reviewed_by_id))


@router.get("/users", response_model=list[ProfileOut])
def list_external_users(user: CurrentUser, db: Session = Depends(get_db)) -> list[ProfileOut]:
    _need_tier(db, user, 2, "외부 사용자 관리")
    rows = db.query(ExternalProfile).filter(ExternalProfile.is_deleted == False).order_by(  # noqa: E712
        ExternalProfile.valid_until).all()
    return [_profile_out(db, p) for p in rows]


@router.patch("/users/{pid}", response_model=ProfileOut)
def update_external_user(pid: UUID, body: ProfileUpdate, user: CurrentUser, db: Session = Depends(get_db)) -> ProfileOut:
    """기간 연장·모듈 변경 — 마스터관리자(권한 확대이므로)."""
    _need_tier(db, user, 3, "외부 사용자 기간·범위 변경")
    p = db.query(ExternalProfile).filter(ExternalProfile.id == pid, ExternalProfile.is_deleted == False).first()  # noqa: E712
    if p is None:
        raise HTTPException(status_code=404, detail="외부 사용자를 찾을 수 없습니다")
    before = {"종료일": str(p.valid_until), "모듈": p.modules}
    if body.valid_until is not None:
        if body.valid_until < p.valid_from:
            raise HTTPException(status_code=422, detail="종료일이 시작일보다 빠릅니다")
        p.valid_until = body.valid_until
    if body.modules is not None:
        p.modules = body.modules
    glog.record(db, p.id, "external_update", version=None, entity_type=ENTITY, before=before,
                after={"종료일": str(p.valid_until), "모듈": p.modules})
    db.commit()
    return _profile_out(db, p)


@router.post("/users/{pid}/revoke", response_model=ProfileOut)
def revoke_external_user(pid: UUID, body: Reason, user: CurrentUser, db: Session = Depends(get_db)) -> ProfileOut:
    """접근 해지 — 즉시 차단(다음 요청부터 403)."""
    _need_tier(db, user, 2, "외부 사용자 해지")
    p = db.query(ExternalProfile).filter(ExternalProfile.id == pid, ExternalProfile.is_deleted == False).first()  # noqa: E712
    if p is None:
        raise HTTPException(status_code=404, detail="외부 사용자를 찾을 수 없습니다")
    p.status, p.closed_reason = EXT_REVOKED, (body.reason or "").strip() or None
    glog.record(db, p.id, "external_revoke", version=None, entity_type=ENTITY, reason=p.closed_reason)
    db.commit()
    return _profile_out(db, p)


class ReviewOut(BaseModel):
    id: UUID
    reviewed_by: str | None
    note: str | None
    count: int
    created_at: datetime


@router.post("/reviews", response_model=ReviewOut, status_code=201)
def record_review(body: Reason, user: CurrentUser, db: Session = Depends(get_db)) -> ReviewOut:
    """분기별 접근 재확인 — 마스터관리자가 현재 외부 사용자 목록을 확인했다는 기록(그때 목록 스냅샷)."""
    _need_tier(db, user, 3, "접근 재확인")
    rows = db.query(ExternalProfile).filter(ExternalProfile.is_deleted == False).all()  # noqa: E712
    now = datetime.now(UTC)
    snap = [_profile_out(db, p).model_dump(mode="json") for p in rows]
    for p in rows:
        p.last_reviewed_at, p.last_reviewed_by_id = now, user.id
    r = AccessReview(reviewed_by_id=user.id, note=(body.reason or "").strip() or None, snapshot=snap)
    db.add(r)
    db.flush()
    glog.record(db, r.id, "access_review", version=None, entity_type=ENTITY, reason=r.note, after={"외부 사용자 수": len(snap)})
    db.commit()
    return ReviewOut(id=r.id, reviewed_by=_name(db, user.id), note=r.note, count=len(snap), created_at=r.created_at)


@router.get("/reviews", response_model=list[ReviewOut])
def list_reviews(user: CurrentUser, db: Session = Depends(get_db)) -> list[ReviewOut]:
    _need_tier(db, user, 2, "외부 사용자 관리")
    rows = db.query(AccessReview).filter(AccessReview.is_deleted == False).order_by(  # noqa: E712
        AccessReview.created_at.desc()).limit(40).all()
    return [ReviewOut(id=r.id, reviewed_by=_name(db, r.reviewed_by_id), note=r.note, count=len(r.snapshot or []),
                      created_at=r.created_at) for r in rows]


# ── 관리자: MFA 초기화(기기 분실) ──
mfa_admin = APIRouter(prefix="/api/users", tags=["user_mgmt"])


@mfa_admin.post("/{user_id}/mfa-reset", status_code=200)
def reset_mfa(user_id: UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    u = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()  # noqa: E712
    if u is None:
        raise HTTPException(status_code=404, detail="User not found")
    u.mfa_secret_enc = u.mfa_pending_enc = None
    u.mfa_enabled_at, u.mfa_recovery = None, None
    db.commit()
    return {"detail": "2단계 인증을 초기화했습니다 — 다음 로그인 때 다시 등록합니다"}
