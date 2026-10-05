"""통제 ↔ 계정 연결 (ADR-0040) — 자동 매칭 · 실무자 수정(초안) · 검토 요청(제안 결재) · 승인 반영.

흐름: 자동 매칭이 초안을 만든다 → 실무자가 드래그로 더하고 뺀다 → "검토 요청" 하면 초안 전체가 제안 묶음
(`proposals`, kind=`control_link`)이 된다 → 책임관리자 1차(항목별) → 마스터 2차 → 승인 항목만 `active`.

자동 매칭 규칙(`scoping_coverage` 의 이름 대조 + 보강):
- `exact` — 정규화 후 같음 / `partial` — 토큰(3자 이상)이 계정명 안에 있음(반대 방향은 제외)
- `alias` — 같은 계정을 부르는 다른 이름(`매출액` ↔ `영업수익`)
- `parent` — 토큰이 **상위 계정**과 맞으면 그 아래 하위 계정에도 잇는다(`영업수익` → 수입수수료·수출 …)
"""
from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.core import governance_log as glog
from app.core.tenant_context import get_active_tenant
from app.models.control_link import (
    ENTITY_CONTROL_LINK,
    L_ACTIVE,
    L_DISMISSED,
    L_DRAFT,
    L_REVIEW,
    SRC_AUTO,
    SRC_MANUAL,
    ControlAccountLink,
)
from app.models.financial_statement import FsAccount
from app.models.proposal import (
    D_ACCEPTED,
    ITEM_LINK_ADD,
    ITEM_LINK_REMOVE,
    KIND_CONTROL_LINK,
    P_PENDING_REVIEW,
    P_REVIEWED,
    Proposal,
    ProposalItem,
)
from app.models.scoping import Scoping, ScopingAccount
from app.services import scoping_coverage as cov
from app.services.control_resolver import resolve_controls, resolve_processes

LINK_STATEMENTS = ("BS", "PL")   # 재무제표 계정으로 잇는 종류. 주석은 이름 키, 현금흐름은 대상 아님
# 같은 계정을 부르는 다른 이름 — 정규화 후 값. 실제 RCM·재무제표에서 확인된 것만 넣는다
ALIASES = {
    "매출액": {"영업수익", "매출"},
    "판매비와관리비": {"영업비용"},
}


class LinkError(ValueError):
    """규칙 위반 — API 409."""


def note_key(name: str) -> str:
    return "note:" + cov.norm(name)


def _alive(db: Session):
    return db.query(ControlAccountLink).filter(ControlAccountLink.is_deleted == False)  # noqa: E712


# ── 계정 목록(오른쪽) ──────────────────────────────────────────
def latest_scoping(db: Session) -> Scoping | None:
    return db.query(Scoping).filter(Scoping.is_deleted == False).order_by(  # noqa: E712
        Scoping.fiscal_year.desc()).first()


def accounts(db: Session) -> list[dict]:
    """연결 대상 계정 — 재무제표 BS·PL 계정 트리 + 최신 스코핑의 주석 계정. 유의 여부는 최신 스코핑 결론."""
    from app.services import scoping as scoping_svc
    sig: dict[str, str | None] = {}
    notes: list[tuple[str, str | None]] = []
    s = latest_scoping(db)
    if s is not None:
        ev = scoping_svc.evaluate(db, s)
        for r in ev["accounts"]:
            a: ScopingAccount = r["account"]
            if a.fs_account_id:
                sig[str(a.fs_account_id)] = r["final"]
            elif a.statement_type == "NOTE":
                notes.append((a.name, r["final"]))
    rows = db.query(FsAccount).filter(FsAccount.is_deleted == False,  # noqa: E712
                                      FsAccount.statement_type.in_(LINK_STATEMENTS)).all()
    by_parent: dict[str | None, list[FsAccount]] = {}
    for a in rows:
        by_parent.setdefault(str(a.parent_id) if a.parent_id else None, []).append(a)
    out: list[dict] = []

    def walk(pid: str | None, depth: int) -> None:
        for a in sorted(by_parent.get(pid, []), key=lambda x: (x.sort_order, x.name)):
            k = str(a.id)
            out.append({"key": k, "fs_account_id": a.id, "name": a.name, "statement_type": a.statement_type,
                        "parent_key": pid, "depth": depth, "has_children": bool(by_parent.get(k)),
                        "significant": sig.get(k)})
            walk(k, depth + 1)

    for st in LINK_STATEMENTS:
        roots = [a for a in by_parent.get(None, []) if a.statement_type == st]
        for a in sorted(roots, key=lambda x: (x.sort_order, x.name)):
            k = str(a.id)
            out.append({"key": k, "fs_account_id": a.id, "name": a.name, "statement_type": st, "parent_key": None,
                        "depth": 0, "has_children": bool(by_parent.get(k)), "significant": sig.get(k)})
            walk(k, 1)
    seen = set()
    for name, final in notes:
        k = note_key(name)
        if k in seen:
            continue
        seen.add(k)
        out.append({"key": k, "fs_account_id": None, "name": name, "statement_type": "NOTE", "parent_key": None,
                    "depth": 0, "has_children": False, "significant": final})
    return out


def controls(db: Session) -> list[dict]:
    procs = {p["code"]: p["name"] for p in resolve_processes(db)}
    return [{"id": c["id"], "code": c.get("code"), "name": c.get("name"), "process_code": c.get("process_code"),
             "process_name": procs.get(c.get("process_code")), "is_key_control": bool(c.get("is_key_control")),
             "related_accounts": c.get("related_accounts")} for c in resolve_controls(db)]


# ── 자동 매칭 ─────────────────────────────────────────────────
def _aliases(token: str) -> set[str]:
    out = set(ALIASES.get(token, set()))
    for k, vs in ALIASES.items():
        if token in vs:
            out |= {k} | (vs - {token})
    return out


def _partial(account_norm: str, token: str, statement_type: str = "BS") -> bool:
    """부분 일치는 **토큰 ⊂ 계정명**(계정이 더 구체적)이 기본 — `차량운반구` → `감가상각누계액_차량운반구`.
    반대 방향(`무형자산상각비` → `무형자산`, `유형자산처분손익` → `유형자산`)은 다른 계정이라 뺀다(운영 데이터 실측).
    예외 둘: 괄호 안 보충이 계정명인 표기(`충당부채(장기근속급여)` → `장기근속급여`), 주석 계정(주제가 넓다 —
    `법인세비용` → 주석 `법인세`)."""
    if len(token) < 3 or token == account_norm or len(account_norm) < 2:
        return False
    if token in account_norm:
        return True
    if account_norm in token:
        inner = re.findall(r"\(([^)]*)\)", token)
        return statement_type == "NOTE" or account_norm in inner
    return False


def suggest(ctrls: list[dict], accts: list[dict]) -> list[tuple[dict, dict, str, str]]:
    """(통제, 계정, match_kind, 토큰) 목록 — 순수 함수(DB 없음). 같은 쌍은 가장 강한 근거 하나만."""
    children: dict[str, list[dict]] = {}
    for a in accts:
        if a["parent_key"]:
            children.setdefault(a["parent_key"], []).append(a)

    def descendants(key: str) -> list[dict]:
        out = []
        for ch in children.get(key, []):
            out.append(ch)
            out += descendants(ch["key"])
        return out

    rank = {"exact": 0, "alias": 1, "parent": 2, "partial": 3}
    best: dict[tuple, tuple] = {}

    def put(c, a, kind, tok):
        k = (str(c["id"]), a["key"])
        if k not in best or rank[kind] < rank[best[k][2]]:
            best[k] = (c, a, kind, tok)

    for c in ctrls:
        for tok in cov.split_tokens(c.get("related_accounts")):
            if tok in cov.ALL_ACCOUNTS_TOKENS:
                continue
            names = {tok} | _aliases(tok)
            for a in accts:
                an = cov.norm(a["name"])
                if an in names:
                    kind = "exact" if an == tok else "alias"
                    put(c, a, kind, tok)
                    for d in descendants(a["key"]):
                        put(c, d, "parent", tok)
                elif _partial(an, tok, a["statement_type"]):
                    put(c, a, "partial", tok)
    return list(best.values())


def run_auto(db: Session) -> dict:
    """자동 매칭 → 초안. 이미 있는 쌍(초안·검토 중·활성·뺀 것)은 건드리지 않는다."""
    ctrls, accts = controls(db), accounts(db)
    existing = {(str(r.control_id), r.account_key) for r in _alive(db).all()}
    added = 0
    for c, a, kind, tok in suggest(ctrls, accts):
        if (str(c["id"]), a["key"]) in existing:
            continue
        db.add(ControlAccountLink(
            control_id=c["id"], control_code=c["code"], control_name=c["name"], fs_account_id=a["fs_account_id"],
            note_key=None if a["fs_account_id"] else a["key"][5:], account_key=a["key"], account_name=a["name"],
            statement_type=a["statement_type"], state=L_DRAFT, source=SRC_AUTO, match_kind=kind, match_token=tok))
        added += 1
    if added:
        glog.record(db, get_active_tenant(), "control_link_auto", version=None, entity_type=ENTITY_CONTROL_LINK,
                    target="자동 매칭", after={"초안 추가": added})
    return {"added": added}


# ── 실무자 수정(초안) ─────────────────────────────────────────
def add_manual(db: Session, control_id: UUID, account_key: str) -> ControlAccountLink:
    c = next((x for x in controls(db) if x["id"] == control_id), None)
    if c is None:
        raise LinkError("통제를 찾을 수 없습니다")
    a = next((x for x in accounts(db) if x["key"] == account_key), None)
    if a is None:
        raise LinkError("계정을 찾을 수 없습니다")
    row = _alive(db).filter(ControlAccountLink.control_id == control_id,
                            ControlAccountLink.account_key == account_key).first()
    if row is not None:
        if row.state == L_DISMISSED:
            row.state, row.source, row.match_kind, row.proposal_id = L_DRAFT, SRC_MANUAL, "manual", None
            return row
        if row.state == L_ACTIVE and row.remove_state == L_DRAFT:
            row.remove_state = None   # 해제 초안을 되돌린 것
            return row
        raise LinkError("이미 연결돼 있거나 연결 초안이 있습니다")
    row = ControlAccountLink(
        control_id=control_id, control_code=c["code"], control_name=c["name"], fs_account_id=a["fs_account_id"],
        note_key=None if a["fs_account_id"] else account_key[5:], account_key=account_key, account_name=a["name"],
        statement_type=a["statement_type"], state=L_DRAFT, source=SRC_MANUAL, match_kind="manual")
    db.add(row)
    return row


def remove(db: Session, row: ControlAccountLink) -> str:
    """초안이면 뺀다(자동 매칭 결과는 '뺀 것'으로 남겨 다시 들어오지 않게), 활성이면 해제 초안."""
    if row.state == L_REVIEW or row.remove_state == L_REVIEW:
        raise LinkError("검토 중인 연결은 바꿀 수 없습니다 — 결재가 끝난 뒤 수정하세요")
    if row.state == L_DRAFT:
        if row.source == SRC_AUTO:
            row.state = L_DISMISSED
            return "dismissed"
        row.is_deleted = True
        return "deleted"
    if row.state == L_ACTIVE:
        if row.remove_state == L_DRAFT:
            row.remove_state = None
            return "restored"
        row.remove_state = L_DRAFT
        return "remove_draft"
    raise LinkError("바꿀 수 없는 상태입니다")


# ── 검토 요청 → 제안 결재 ────────────────────────────────────
def open_proposal(db: Session) -> Proposal | None:
    return db.query(Proposal).filter(Proposal.kind == KIND_CONTROL_LINK, Proposal.is_deleted == False,  # noqa: E712
                                     Proposal.status.in_([P_PENDING_REVIEW, P_REVIEWED])).first()


def submit(db: Session, user_id: UUID, user_name: str, note: str | None) -> Proposal:
    from app.services import proposals as psvc
    if open_proposal(db) is not None:
        raise LinkError("결재 중인 연결 묶음이 있습니다 — 끝난 뒤 다시 요청하세요")
    adds = _alive(db).filter(ControlAccountLink.state == L_DRAFT).all()
    removes = _alive(db).filter(ControlAccountLink.state == L_ACTIVE, ControlAccountLink.remove_state == L_DRAFT).all()
    if not adds and not removes:
        raise LinkError("검토 요청할 변경이 없습니다")
    items = []
    for r in sorted(adds, key=lambda x: (x.control_code or "", x.account_name)):
        why = {"exact": "이름 일치", "alias": "같은 계정의 다른 이름", "parent": "상위 계정 연결의 하위",
               "partial": "이름 일부 일치"}.get(r.match_kind or "", "")
        items.append(dict(action=ITEM_LINK_ADD, account_id=r.fs_account_id, statement_type=r.statement_type,
                          account_name=r.account_name, control_id=r.control_id, control_code=r.control_code,
                          control_name=r.control_name, link_id=r.id,
                          rationale=(f"자동 — RCM 관련 계정 '{r.match_token}' {why}" if r.source == SRC_AUTO
                                     else f"수동 연결 — {user_name}")))
    for r in sorted(removes, key=lambda x: (x.control_code or "", x.account_name)):
        items.append(dict(action=ITEM_LINK_REMOVE, account_id=r.fs_account_id, statement_type=r.statement_type,
                          account_name=r.account_name, control_id=r.control_id, control_code=r.control_code,
                          control_name=r.control_name, link_id=r.id, rationale=f"연결 해제 요청 — {user_name}"))
    p = psvc.create(db, kind=KIND_CONTROL_LINK, title=f"통제 ↔ 계정 연결 {len(adds)}건 추가·{len(removes)}건 해제",
                    summary=(note or "").strip() or None, proposed_by=f"user:{user_id}", items=items)
    p.requested_by_id = user_id
    for r in adds:
        r.state, r.proposal_id = L_REVIEW, p.id
    for r in removes:
        r.remove_state, r.proposal_id = L_REVIEW, p.id
    return p


def apply_approved(db: Session, p: Proposal, items: list[ProposalItem]) -> dict:
    """2차 승인 반영 — 승인 항목은 활성/해제, 반려 항목은 되돌린다(추가 반려 = 뺀 것, 해제 반려 = 유지)."""
    added = removed = rejected = 0
    for i in items:
        row = db.get(ControlAccountLink, i.link_id) if i.link_id else None
        if row is None or row.is_deleted:
            continue
        ok = i.decision == D_ACCEPTED
        if i.action == ITEM_LINK_ADD:
            row.state, row.proposal_id = (L_ACTIVE if ok else L_DISMISSED), None
            added += ok
        else:
            if ok:
                row.is_deleted = True
                removed += 1
            else:
                row.remove_state, row.proposal_id = None, None
        rejected += not ok
    return {"linked": added, "unlinked": removed, "rejected": rejected}


def revert_returned(db: Session, p: Proposal) -> None:
    """묶음 반려 — 검토 중이던 것을 초안으로 되돌린다(고쳐서 다시 요청)."""
    for r in _alive(db).filter(ControlAccountLink.proposal_id == p.id).all():
        if r.state == L_REVIEW:
            r.state = L_DRAFT
        if r.remove_state == L_REVIEW:
            r.remove_state = L_DRAFT
        r.proposal_id = None


def board(db: Session) -> dict:
    rows = _alive(db).filter(ControlAccountLink.state != L_DISMISSED).all()
    p = open_proposal(db)
    return {
        "controls": controls(db), "accounts": accounts(db),
        "links": [{"id": r.id, "control_id": r.control_id, "account_key": r.account_key, "state": r.state,
                   "remove_state": r.remove_state, "source": r.source, "match_kind": r.match_kind,
                   "match_token": r.match_token} for r in rows],
        "dismissed": _alive(db).filter(ControlAccountLink.state == L_DISMISSED).count(),
        "open_proposal": {"id": p.id, "status": p.status, "title": p.title} if p else None,
    }


def active_by_account(db: Session) -> dict[str, list[ControlAccountLink]]:
    out: dict[str, list[ControlAccountLink]] = {}
    for r in _alive(db).filter(ControlAccountLink.state == L_ACTIVE).all():
        out.setdefault(r.account_key, []).append(r)
    return out


