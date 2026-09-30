"""회사 계정 ↔ 스코핑 템플릿 계정 매칭 (8-C, ADR-0037 §4).

원칙 (마스터 확정 D3~D7, `prompts/ICFR_backend_fs-8c_20260929.md`):
- **자동 매칭은 제안일 뿐이다.** 제안은 저장하지 않는다. 사람이 확인한 링크만 `fs_template_links` 에 남긴다.
- **근거는 서버가 판정한다** — 클라이언트가 보낸 값을 믿지 않는다. 이름 규칙으로 설명되면 `exact`/`normalized`,
  아니면 `manual`. 기록된 근거가 실제 이름과 어긋날 수 없게 하기 위해서다.
- 제안 규칙: `exact`(공백 제거 동일) → `normalized`(접두 번호·괄호 접미·밑줄 접미를 뗀 뒤 동일) —
  **템플릿 후보가 1개일 때만.** 회사 계정 이름이 반복되면(`감가상각누계액` 이 여러 공시 행 아래) 제안하지 않는다.
- 회사 계정 1개 × 템플릿 버전당 활성 링크 1개. 템플릿 계정 하나에 여러 회사 계정 — 허용, 경고.

실측(8-C STEP 0): 정산표를 붙인 마스터(8-B2)에서 템플릿 BS 55/58·PL 44/45 가 정확일치.
"""
import re
from collections import Counter
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.financial_statement import (
    FS_LINK_EXACT,
    FS_LINK_MANUAL,
    FS_LINK_NORMALIZED,
    FsAccount,
    FsTemplateLink,
)
from app.models.scoping import DEFAULT_TEMPLATE_CODE, ScopingTemplate, ScopingTemplateAccount
from app.services.financial_statement import FsError, FsNotFoundError, get_account
from app.services.fs_upload.cells import norm, split_prefix

_PAREN_RE = re.compile(r"\([^)]*\)")


def exact_key(name: str | None) -> str:
    return norm(name)


def normalized_key(name: str | None) -> str:
    """접두 번호("2. 이자의 수취")·괄호 접미("대손충당금(매출채권)")·밑줄 접미("정부보조금_비품")·끝 콜론을 뗀다."""
    t = split_prefix(name or "")[1]
    t = _PAREN_RE.sub("", t)
    t = t.split("_", 1)[0]
    return norm(t).rstrip(":：")


def judge(account_name: str, template_name: str) -> str:
    if exact_key(account_name) == exact_key(template_name):
        return FS_LINK_EXACT
    if normalized_key(account_name) and normalized_key(account_name) == normalized_key(template_name):
        return FS_LINK_NORMALIZED
    return FS_LINK_MANUAL


def _alive(model):
    return model.is_deleted == False  # noqa: E712


def get_template(db: Session, code: str | None, version: int | None) -> ScopingTemplate:
    """템플릿 — 버전을 안 주면 그 코드의 최신 버전."""
    q = select(ScopingTemplate).where(ScopingTemplate.code == (code or DEFAULT_TEMPLATE_CODE),
                                      _alive(ScopingTemplate))
    if version is not None:
        q = q.where(ScopingTemplate.version == version)
    t = db.scalars(q.order_by(ScopingTemplate.version.desc())).first()
    if t is None:
        raise FsNotFoundError(f"템플릿을 찾을 수 없습니다: {code or DEFAULT_TEMPLATE_CODE} v{version or '최신'}")
    return t


def template_accounts(db: Session, template: ScopingTemplate, statement_type: str | None = None
                      ) -> list[ScopingTemplateAccount]:
    q = select(ScopingTemplateAccount).where(ScopingTemplateAccount.template_id == template.id,
                                             _alive(ScopingTemplateAccount))
    if statement_type is not None:
        q = q.where(ScopingTemplateAccount.statement_type == statement_type)
    return list(db.scalars(q.order_by(ScopingTemplateAccount.statement_type, ScopingTemplateAccount.sort_order)))


def active_links(db: Session, template: ScopingTemplate) -> list[FsTemplateLink]:
    return list(db.scalars(select(FsTemplateLink).where(
        FsTemplateLink.template_code == template.code, FsTemplateLink.template_version == template.version,
        _alive(FsTemplateLink))).all())


def suggest(accounts: list[FsAccount], tmpl: list[ScopingTemplateAccount]) -> dict[UUID, tuple[ScopingTemplateAccount, str] | None]:
    """회사 계정별 제안 (템플릿 계정, 근거) — 저장하지 않는다. 순수 함수.

    반복 이름 판정은 **잎(소계 아닌 계정)끼리만** 센다. 공시 행과 그 아래 COA 잎이 같은 이름이면
    ("현금및현금성자산" 공시 행 ⊃ "현금및현금성자산" 잎 — 8-B2 결합 결과) 템플릿이 COA 입도이므로 **잎에 제안**하고
    공시 행에는 제안하지 않는다(실측: 이 규칙 전 BS 템플릿 적용 42 → 후 48).
    """
    leaves = Counter(exact_key(a.name) for a in accounts if not a.is_subtotal)
    subtotals = Counter(exact_key(a.name) for a in accounts if a.is_subtotal)
    by_exact: dict[str, list[ScopingTemplateAccount]] = {}
    by_norm: dict[str, list[ScopingTemplateAccount]] = {}
    for t in tmpl:
        by_exact.setdefault(exact_key(t.name), []).append(t)
        by_norm.setdefault(normalized_key(t.name), []).append(t)
    out: dict[UUID, tuple[ScopingTemplateAccount, str] | None] = {}
    for a in accounts:
        out[a.id] = None
        k = exact_key(a.name)
        if (a.is_subtotal and (leaves[k] or subtotals[k] > 1)) or (not a.is_subtotal and leaves[k] > 1):
            continue
        cands = by_exact.get(exact_key(a.name), [])
        if len(cands) == 1:
            out[a.id] = (cands[0], FS_LINK_EXACT)
            continue
        if cands:
            continue    # 템플릿에 같은 이름이 여럿 — 사람이 고른다
        cands = by_norm.get(normalized_key(a.name), []) if normalized_key(a.name) else []
        if len(cands) == 1:
            out[a.id] = (cands[0], FS_LINK_NORMALIZED)
    return out


def matches(db: Session, statement_type: str, code: str | None, version: int | None) -> dict:
    """회사 계정별 현재 링크 + 제안 + 템플릿 계정별 연결 수."""
    template = get_template(db, code, version)
    tmpl = template_accounts(db, template, statement_type)
    tmpl_by_id = {t.id: t for t in tmpl}
    accounts = list(db.scalars(select(FsAccount).where(FsAccount.statement_type == statement_type,
                                                       _alive(FsAccount))
                               .order_by(FsAccount.sort_order, FsAccount.created_at)).all())
    by_id = {a.id: a for a in accounts}
    links = {lk.account_id: lk for lk in active_links(db, template) if lk.account_id in by_id}
    sugg = suggest(accounts, tmpl)
    linked_count = Counter(lk.template_account_id for lk in links.values())

    def depth(a: FsAccount) -> int:
        d, cur, seen = 0, a, set()
        while cur.parent_id in by_id and cur.id not in seen:
            seen.add(cur.id)
            d, cur = d + 1, by_id[cur.parent_id]
        return d

    rows = []
    for a in _tree_order(accounts):
        lk = links.get(a.id)
        s = sugg[a.id]
        rows.append({
            "account_id": a.id, "name": a.name, "is_subtotal": a.is_subtotal, "depth": depth(a),
            "parent_name": by_id[a.parent_id].name if a.parent_id in by_id else None,
            "link": None if lk is None else _link_payload(lk, tmpl_by_id.get(lk.template_account_id)),
            "suggestion": None if s is None else {"template_account_id": s[0].id, "template_name": s[0].name,
                                                  "basis": s[1]},
        })
    counts = Counter()
    for r in rows:
        counts["accounts"] += 1
        if r["link"]:
            counts["linked"] += 1
        elif r["suggestion"]:
            counts[f"suggested_{r['suggestion']['basis']}"] += 1
        else:
            counts["unmatched"] += 1
    return {
        "template_code": template.code, "template_version": template.version, "statement_type": statement_type,
        "accounts": rows,
        "template_accounts": [{"id": t.id, "name": t.name, "group_label": t.group_label, "sort_order": t.sort_order,
                               "linked_count": linked_count.get(t.id, 0)} for t in tmpl],
        "counts": dict(counts),
    }


def _tree_order(accounts: list[FsAccount]) -> list[FsAccount]:
    """트리 순서(부모 → 자식, 형제는 sort_order). `sort_order` 는 원본 행 번호라 공시·정산표 행이 섞이면
    평면 정렬로는 뒤섞인다 — 화면이 트리처럼 읽히게 깊이 우선으로 편다."""
    ids = {a.id for a in accounts}
    kids: dict[UUID | None, list[FsAccount]] = {}
    for a in accounts:
        kids.setdefault(a.parent_id if a.parent_id in ids else None, []).append(a)
    out: list[FsAccount] = []

    def walk(pid: UUID | None) -> None:
        for a in sorted(kids.get(pid, []), key=lambda x: (x.sort_order, x.created_at)):
            out.append(a)
            walk(a.id)
    walk(None)
    return out


def _link_payload(lk: FsTemplateLink, t: ScopingTemplateAccount | None) -> dict:
    return {"id": lk.id, "account_id": lk.account_id, "template_account_id": lk.template_account_id,
            "template_name": t.name if t else None, "template_code": lk.template_code,
            "template_version": lk.template_version, "basis": lk.basis, "confirmed_by_id": lk.confirmed_by_id,
            "confirmed_at": lk.confirmed_at, "note": lk.note}


def confirm(db: Session, code: str | None, version: int | None, pairs: list[dict], actor_id: UUID
            ) -> tuple[list[dict], list[str]]:
    """사람이 확인한 링크 저장. 같은 회사 계정의 기존 활성 링크는 대체(소프트 삭제 후 새로)."""
    template = get_template(db, code, version)
    tmpl = {t.id: t for t in template_accounts(db, template)}
    seen = Counter(str(p["account_id"]) for p in pairs)
    twice = [k for k, n in seen.items() if n > 1]
    if twice:
        raise FsError(f"같은 회사 계정을 두 번 연결했습니다: {', '.join(twice)}")
    existing = {lk.account_id: lk for lk in active_links(db, template)}
    now = datetime.now(UTC)
    out = []
    for p in pairs:
        account = get_account(db, UUID(str(p["account_id"])))
        t = tmpl.get(UUID(str(p["template_account_id"])))
        if t is None:
            raise FsError(f"템플릿 {template.code} v{template.version} 에 없는 템플릿 계정입니다: {p['template_account_id']}")
        if t.statement_type != account.statement_type:
            raise FsError(f"'{account.name}'({account.statement_type}) 과 '{t.name}'({t.statement_type}) 은 "
                          "재무제표 종류가 다릅니다")
        old = existing.get(account.id)
        if old is not None and old.template_account_id == t.id:
            out.append(_link_payload(old, t))
            continue
        if old is not None:
            old.is_deleted = True
            db.flush()   # 부분 유니크 — 옛 링크를 먼저 내려야 새 링크를 넣을 수 있다
        lk = FsTemplateLink(account_id=account.id, template_account_id=t.id, template_code=template.code,
                            template_version=template.version, basis=judge(account.name, t.name),
                            confirmed_by_id=actor_id, confirmed_at=now, note=(p.get("note") or None))
        db.add(lk)
        db.flush()
        existing[account.id] = lk
        out.append(_link_payload(lk, t))
    warnings = []
    per_template = Counter(lk.template_account_id for lk in existing.values() if not lk.is_deleted)
    for tid, n in per_template.items():
        if n > 1 and tid in {UUID(str(p["template_account_id"])) for p in pairs}:
            warnings.append(f"템플릿 계정 '{tmpl[tid].name}' 에 회사 계정 {n}개가 연결돼 있습니다")
    return out, warnings


def unlink(db: Session, link_id: UUID) -> None:
    lk = db.scalars(select(FsTemplateLink).where(FsTemplateLink.id == link_id, _alive(FsTemplateLink))).first()
    if lk is None:
        raise FsNotFoundError("링크를 찾을 수 없습니다")
    lk.is_deleted = True
    db.flush()
