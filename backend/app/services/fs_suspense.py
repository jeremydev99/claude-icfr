"""임시계정(원본 차이) — 소계 불일치를 받아 두고 ICFR 관리자가 검토해 반영한다 (ADR-0037 §2.13).

마스터 지시(2026-09-30): "자본계정 금액 차이 나는 부분은 임시계정으로 일단 넣어 놓고 ICFR 관리자가 확인하여
변경사항을 반영할 수 있도록." 실측 사례: `BS정산표` 지배주주지분 수식 누락 → 전 연도 2.3~2.5억 차.

흐름:
1. **흡수**(`absorb`) — 업로드·결합 후 검증에서 `subtotal` 불일치가 나오면, 그 소계 아래 `임시계정(원본 차이)`
   계정에 **차액(소계 실제 − 하위 합)** 을 넣는다. 원본 숫자는 하나도 바꾸지 않는다 — 합계가 맞아 떨어지고 차이가
   어디에 얼마 있는지 드러난다. 금액 행 `raw_meta.suspense = true`.
2. **확정 차단** — 미해결 임시계정이 있으면 8-A `validate()` 가 `suspense_unresolved` 오류를 낸다.
3. **해소**(`resolve`, `icfr_manager`, draft 에서만) — 셋 중 하나. 누가·언제·사유가 `raw_meta.resolved` 에 남는다.
   - `fix_subtotal` — 원본 소계가 틀렸다: 소계 금액을 하위 합으로 정정(원래 값은 `raw_meta.corrected_from`)하고
     임시계정 행을 소프트 삭제.
   - `reclass` — 하위 계정 하나가 빠졌거나 틀렸다: 차액을 **같은 소계 아래 형제 계정**으로 옮기고 임시계정 행 삭제.
     형제로만 제한한다 — 다른 곳으로 옮기면 소계가 다시 어긋난다.
   - `accept` — 차이를 그대로 두되 검토했음을 사유와 함께 남긴다(확정 허용).

균형(자산=부채+자본) 불일치는 받아 줄 소계가 없어 흡수하지 않는다 — 오류로 남는다.
"""
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.financial_statement import FsAccount, FsAmount, FsStatement
from app.services import financial_statement as svc

SUSPENSE_NAME = "임시계정(원본 차이)"
ACTION_FIX_SUBTOTAL = "fix_subtotal"
ACTION_RECLASS = "reclass"
ACTION_ACCEPT = "accept"
ACTIONS = (ACTION_FIX_SUBTOTAL, ACTION_RECLASS, ACTION_ACCEPT)


def _alive(model):
    return model.is_deleted == False  # noqa: E712


def _suspense_account(db: Session, parent: FsAccount) -> FsAccount:
    """소계 아래 임시계정 — 있으면 재사용. 이름은 사람이 알아보라고 붙인 것이며 판정은 금액 행 표식으로 한다."""
    acc = db.scalars(select(FsAccount).where(FsAccount.parent_id == parent.id, FsAccount.name == SUSPENSE_NAME,
                                             _alive(FsAccount))).first()
    if acc is None:
        acc = svc.create_account(db, statement_type=parent.statement_type, name=SUSPENSE_NAME, section=parent.section,
                                 parent_id=parent.id, sort_order=10 ** 6, is_subtotal=False, rollup_sign=1)
    return acc


def absorb(db: Session, statement: FsStatement, result: dict, *, source: str) -> list[dict]:
    """검증 결과의 소계 불일치를 임시계정으로 받는다. 받은 목록을 돌려준다(없으면 빈 목록).

    차액 = 소계 실제 − 하위 합(검증 `diff`). 임시계정은 합산 부호 +1 이므로 넣고 나면 그 소계가 맞는다.
    각 소계는 자기 금액(실제값)으로 윗 소계에 들어가므로 불일치마다 독립으로 받으면 된다.
    """
    out = []
    for e in result["errors"]:
        if e["rule"] != svc.RULE_SUBTOTAL or e["account_id"] is None or not e["diff"]:
            continue
        parent = svc.get_account(db, e["account_id"])
        acc = _suspense_account(db, parent)
        existing = db.scalars(select(FsAmount).where(FsAmount.statement_id == statement.id,
                                                     FsAmount.account_id == acc.id, _alive(FsAmount))).first()
        if existing is not None and (existing.raw_meta or {}).get("resolved"):
            continue    # 검토(accept)된 행에 덧붙이면 검토 기록이 덮인다 — 불일치 오류로 남긴다
        amount = Decimal(e["diff"]) + (existing.amount or 0 if existing is not None else 0)
        svc.set_amount(db, statement, acc, amount, raw_label=SUSPENSE_NAME, raw_meta={
            "suspense": True, "source": source, "parent_account_id": str(parent.id), "parent_name": parent.name,
            "expected": str(e["expected"]), "actual": str(e["actual"]), "diff": str(amount)})
        out.append({"parent_account_id": parent.id, "parent_name": parent.name, "amount": amount})
    return out


def items(db: Session, statement: FsStatement) -> list[dict]:
    """재무제표의 임시계정 행(해소된 것 포함 — 소프트 삭제된 해소 이력도 보여 준다)."""
    rows = db.execute(select(FsAmount, FsAccount).join(FsAccount, FsAccount.id == FsAmount.account_id)
                      .where(FsAmount.statement_id == statement.id)).all()
    out = []
    for r, a in rows:
        if not svc.is_suspense(r):
            continue
        meta = r.raw_meta or {}
        if not meta.get("resolved") and not r.amount:
            continue    # 재계산으로 비워진 행 — 차이가 사라졌다
        out.append({"amount_id": r.id, "account_id": a.id, "parent_account_id": a.parent_id,
                    "parent_name": meta.get("parent_name"), "amount": r.amount,
                    "source_amount": Decimal(meta["diff"]) if meta.get("diff") else r.amount,
                    "expected": meta.get("expected"), "actual": meta.get("actual"),
                    "resolved": meta.get("resolved"), "is_deleted": r.is_deleted})
    return sorted(out, key=lambda x: (x["is_deleted"], str(x["parent_name"])))


def _amount_row(db: Session, statement: FsStatement, account_id: UUID) -> FsAmount | None:
    return db.scalars(select(FsAmount).where(FsAmount.statement_id == statement.id,
                                             FsAmount.account_id == account_id, _alive(FsAmount))).first()


def resolve(db: Session, statement: FsStatement, amount_id: UUID, action: str, reason: str | None,
            actor_id: UUID, target_account_id: UUID | None = None) -> dict:
    """임시계정 해소. draft 에서만(확정 후엔 재오픈). 결과 행 정보를 돌려준다."""
    if statement.status != "draft":
        raise svc.FsConflictError("확정된 재무제표입니다 — 재오픈 후 해소하세요")
    if svc.in_review(db, statement):
        raise svc.FsConflictError("검토 중인 재무제표입니다 — 회수·반려 후 해소하세요")
    if action not in ACTIONS:
        raise svc.FsError(f"해소 방법이 올바르지 않습니다: {action} (가능: {', '.join(ACTIONS)})")
    reason = (reason or "").strip()
    if not reason:
        raise svc.FsError("해소 사유가 필요합니다")
    row = db.scalars(select(FsAmount).where(FsAmount.id == amount_id, FsAmount.statement_id == statement.id,
                                            _alive(FsAmount))).first()
    if row is None or not svc.is_suspense(row):
        raise svc.FsNotFoundError("임시계정 금액 행을 찾을 수 없습니다")
    if row.raw_meta.get("resolved"):
        raise svc.FsConflictError("이미 해소된 임시계정입니다")
    account = svc.get_account(db, row.account_id)
    parent = svc.get_account(db, account.parent_id)
    amt = row.amount or Decimal(0)
    record = {"action": action, "reason": reason, "by": str(actor_id), "at": datetime.now(UTC).isoformat(),
              "amount": str(amt)}

    if action == ACTION_FIX_SUBTOTAL:
        prow = _amount_row(db, statement, parent.id)
        if prow is None or prow.amount is None:
            raise svc.FsError("정정할 소계 금액이 없습니다")
        meta = dict(prow.raw_meta or {})
        meta.setdefault("corrected_from", str(prow.amount))
        meta["corrected"] = record
        prow.amount, prow.raw_meta = prow.amount - amt, meta
    elif action == ACTION_RECLASS:
        if target_account_id is None:
            raise svc.FsError("옮길 계정(target_account_id)이 필요합니다")
        target = svc.get_account(db, target_account_id)
        if target.parent_id != parent.id or target.id == account.id:
            raise svc.FsError("임시계정과 같은 소계 아래의 다른 계정으로만 옮길 수 있습니다")
        trow = _amount_row(db, statement, target.id)
        if trow is None:
            trow = svc.set_amount(db, statement, target, Decimal(0))
        meta = dict(trow.raw_meta or {})
        meta.setdefault("reclassed_from", str(trow.amount or 0))
        meta.setdefault("reclassed", []).append(record)
        trow.amount, trow.raw_meta = (trow.amount or Decimal(0)) + amt, meta
        record["target_account_id"] = str(target.id)
    meta = dict(row.raw_meta)
    meta["resolved"] = record
    row.raw_meta = meta
    if action in (ACTION_FIX_SUBTOTAL, ACTION_RECLASS):
        row.is_deleted = True   # 감사 컬럼이 누가·언제를 남기고, 해소 이력은 raw_meta 에 남는다
    db.flush()
    rebalance(db, statement, source=f"rebalance:{action}")
    return {"amount_id": row.id, "action": action, "resolved": record}


def rebalance(db: Session, statement: FsStatement, *, source: str) -> list[dict]:
    """미해결 임시계정을 다시 계산한다 — 한 곳을 고치면 연쇄된 차이가 바뀌기 때문이다.

    예: 지배주주지분(+차액)을 소계 정정하면 자본총계 아래 −차액은 틀린 값이 된다. 미해결 행을 0 으로 비우고
    검증 → 흡수를 다시 하면 남은 불일치만 임시계정에 남는다. **해소(accept)된 행은 건드리지 않는다.**
    """
    rows = db.execute(select(FsAmount).where(FsAmount.statement_id == statement.id, _alive(FsAmount))).scalars()
    for r in rows:
        if svc.is_unresolved_suspense(r):
            r.amount = Decimal(0)
    db.flush()
    return absorb(db, statement, svc.validate(db, statement), source=source)
