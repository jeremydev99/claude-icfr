"""변경 이력 자동 기록 — 거버넌스 대상 문서의 값 변경·항목 확인을 `governance_events` 에 쌓는다 (ADR-0038 §2.4).

엔드포인트마다 "고치기 전 값"을 챙기게 하면 한 곳만 빠뜨려도 이력이 빈다. 그래서 **flush 직전 ORM 의 속성 이력**
(`inspect(obj).attrs[x].history`)에서 전·후 값을 뽑는다 — 어떤 경로로 바뀌든 남는다(감사 컬럼 ADR-0036 과 같은 발상).

- 기록 대상: `GOVERNED` 의 모델. 1단계는 스코핑(본문·계정·벤치마크·조정·문구·항목 출처).
- 새로 만든 행은 조정 항목만 기록한다(스코핑 생성 때 계정 200여 행이 한꺼번에 생기는 것은 변경이 아니다).
- 항목 출처(`scoping_field_origins`)의 상태 변화는 값 변경이 아니라 **확인/확인 취소**로 기록하고,
  취소 전 확인자를 `before` 에 남긴다 — 현재 행에서 확인자가 지워져도 이력에는 남는다.
- 상태 전이(검토 요청·승인·재오픈)는 API 가 `record()` 로 직접 남긴다(사유가 필요하므로). 여기서는 그 칸들을 제외한다.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.core.audit_context import get_current_actor, resolve_actor
from app.core.tenant_context import get_active_tenant
from app.models.governance import (
    ENTITY_SCOPING,
    EV_ITEM_CONFIRM,
    EV_ITEM_UNCONFIRM,
    EV_VALUE_CHANGE,
    GovernanceEvent,
)
from app.models.scoping import (
    ORIGIN_CONFIRMED,
    ORIGIN_TEMPLATE,
    Scoping,
    ScopingAccount,
    ScopingAdjustment,
    ScopingBenchmark,
    ScopingFieldOrigin,
    ScopingText,
)

# 모든 모델 공통으로 이력에서 빼는 칸 — 기록 장치 자체이거나 식별자
_SKIP = {"id", "tenant_id", "created_at", "created_by", "updated_at", "updated_by", "deleted_at", "deleted_by",
         "row_version", "scoping_id"}
# 스코핑 본문에서 빼는 칸 — 상태 전이는 API 가 사유와 함께 직접 기록한다
_SCOPING_STATE = {"status", "confirmed_at", "confirmed_by_id", "confirm_reason", "confirm_badge_count",
                  "confirmed_snapshot", "review_requested_by_id", "review_requested_at", "review_path",
                  "reviewed_by_id", "reviewed_at", "version"}

FIELD_LABELS = {
    "selected_benchmark": "선택 벤치마크", "smt_rate": "수행중요성 설정율", "rationale": "중요성 설정근거",
    "base_fiscal_year": "기준 재무제표 연도", "smt_guide_low": "설정율 가이드 하한", "smt_guide_high": "설정율 가이드 상한",
    "qual_threshold": "질적 기준값", "qual_comparison": "질적 비교 방식", "review_auditor": "감사인",
    "review_date": "감사인 검토일", "review_opinion": "감사인 의견", "review_evidence_ref": "검토 증빙",
    "ratings": "질적 평가", "qual_basis": "질적 판단 근거", "manual_conclusion": "수동 판정", "manual_reason": "수동 판정 사유",
    "current_amount": "당기 금액", "prior_amount": "전기 금액", "base_amount": "기준값", "rate": "비율",
    "guide_low": "가이드 하한", "guide_high": "가이드 상한", "body": "문구", "amount": "금액", "reason": "사유",
    "is_deleted": "삭제",
}


def _json(v):
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, datetime | date):
        return v.isoformat()
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, dict):
        return {k: _json(x) for k, x in v.items()}
    if isinstance(v, list | tuple):
        return [_json(x) for x in v]
    return v


def _actor_uuid() -> UUID | None:
    a = get_current_actor()
    try:
        return UUID(a) if a and not a.startswith("system:") else None
    except ValueError:
        return None


def _scoping_of(session: Session, obj) -> Scoping | None:
    sid = obj.id if isinstance(obj, Scoping) else getattr(obj, "scoping_id", None)
    return session.get(Scoping, sid) if sid else None


def _target(session: Session, obj) -> str:
    if isinstance(obj, ScopingAccount):
        return f"계정 {obj.name}"
    if isinstance(obj, ScopingBenchmark):
        return f"벤치마크 {obj.kind}"
    if isinstance(obj, ScopingText):
        return f"문구 {obj.title or obj.key}"
    if isinstance(obj, ScopingAdjustment):
        return "조정 항목"
    if isinstance(obj, ScopingFieldOrigin):
        tgt = {"account": ScopingAccount, "benchmark": ScopingBenchmark, "text": ScopingText}.get(obj.target_type)
        row = session.get(tgt, obj.target_id) if tgt else None
        name = _target(session, row) if row is not None else "중요성 기준"
        return f"{name} · {FIELD_LABELS.get(obj.field, obj.field)}"
    return "스코핑"


def _changes(obj, skip: set[str]) -> tuple[dict, dict]:
    before, after = {}, {}
    state = inspect(obj)
    for attr in state.mapper.column_attrs:
        key = attr.key
        if key in skip:
            continue
        h = state.attrs[key].history
        if not h.has_changes():
            continue
        old = h.deleted[0] if h.deleted else None
        new = h.added[0] if h.added else None
        if old == new:
            continue
        label = FIELD_LABELS.get(key, key)
        before[label], after[label] = _json(old), _json(new)
    return before, after


def _event(session: Session, s: Scoping | None, entity_id, action: str, target: str, before, after) -> GovernanceEvent:
    ev = GovernanceEvent(entity_type=ENTITY_SCOPING, entity_id=entity_id, action=action, target=target[:300],
                         actor_id=_actor_uuid(), before=before or None, after=after or None,
                         version=s.version if s is not None else None)
    # 리스너 실행 순서에 기대지 않는다 — 테넌트·행위자를 직접 찍는다(두 리스너 모두 이미 있는 값은 보존한다)
    ev.tenant_id = get_active_tenant()
    actor = resolve_actor(session)
    ev.created_by = ev.updated_by = actor
    return ev


@event.listens_for(Session, "before_flush")
def _log_governed_changes(session: Session, flush_context, instances) -> None:
    if get_active_tenant() is None:
        return   # 시드·마이그레이션 같은 테넌트 밖 작업은 대상이 아니다
    if session.info.get("governance_bulk"):
        return   # 대량 교체(재무제표에서 다시 불러오기) — 호출자가 요약 1건을 직접 남긴다
    out: list[GovernanceEvent] = []
    with session.no_autoflush:
        for obj in list(session.dirty):
            if not session.is_modified(obj, include_collections=False):
                continue
            if isinstance(obj, ScopingFieldOrigin):
                h = inspect(obj).attrs["status"].history
                if not h.has_changes():
                    continue
                old = h.deleted[0] if h.deleted else None
                new = obj.status
                if old == ORIGIN_TEMPLATE and new == ORIGIN_CONFIRMED:
                    action, before = EV_ITEM_CONFIRM, None
                elif old == ORIGIN_CONFIRMED and new == ORIGIN_TEMPLATE:
                    by = inspect(obj).attrs["confirmed_by_id"].history
                    action = EV_ITEM_UNCONFIRM
                    before = {"확인자": _json(by.deleted[0] if by.deleted else obj.confirmed_by_id)}
                else:
                    continue   # → edited 는 값 변경 이벤트가 따로 남는다
                s = session.get(Scoping, obj.scoping_id)
                out.append(_event(session, s, obj.scoping_id, action, _target(session, obj), before, None))
                continue
            if isinstance(obj, Scoping | ScopingAccount | ScopingBenchmark | ScopingAdjustment | ScopingText):
                skip = _SKIP | (_SCOPING_STATE if isinstance(obj, Scoping) else set())
                before, after = _changes(obj, skip)
                if not before and not after:
                    continue
                s = _scoping_of(session, obj)
                out.append(_event(session, s, s.id if s else obj.id, EV_VALUE_CHANGE, _target(session, obj),
                                  before, after))
        for obj in list(session.new):
            if isinstance(obj, ScopingAdjustment):
                s = _scoping_of(session, obj)
                out.append(_event(session, s, obj.scoping_id, EV_VALUE_CHANGE, "조정 항목 추가", None,
                                  {"금액": obj.amount, "사유": obj.reason}))
    for ev in out:
        session.add(ev)


def record(db: Session, entity_id, action: str, *, version: int | None, target: str | None = None,
           reason: str | None = None, before: dict | None = None, after: dict | None = None,
           entity_type: str = ENTITY_SCOPING) -> GovernanceEvent:
    """상태 전이 등 API 가 직접 남기는 이력(사유 포함). 문서 종류는 `entity_type`(기본 스코핑)."""
    ev = GovernanceEvent(entity_type=entity_type, entity_id=entity_id, action=action, target=target,
                         actor_id=_actor_uuid(), reason=reason, before=_json(before) if before else None,
                         after=_json(after) if after else None, version=version)
    db.add(ev)
    return ev
