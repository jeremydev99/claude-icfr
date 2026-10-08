"""감사 로그 대상 이름 — 대상 종류 + ID → 사람이 읽는 이름(코드·명칭). 기록 시점에 찍어 둔다(이후 이름이 바뀌어도 그때 이름).

못 찾으면 None(로그에는 ID 만 남는다). 조회 실패가 기록을 막지 않도록 호출부가 예외를 삼킨다.
"""
from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

REPORT_DOCS = {
    "meta": "보고 패키지 기본 정보", "ops_report": "운영실태보고서", "ac_report": "감사위원회 평가보고서",
    "board_ops": "이사회 보고(운영실태 결과)", "ac_eval": "이사회 보고(감사위원회 평가결과)",
    "ac_minutes": "감사위원회 의사록(안)", "board_minutes": "이사회 의사록(안)",
}


def _j(*parts) -> str:
    return " ".join(str(p) for p in parts if p not in (None, ""))


def _short(s: str | None, n: int = 40) -> str | None:
    if not s:
        return None
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _get(db, model, oid):
    try:
        return db.get(model, oid if isinstance(oid, UUID) else UUID(str(oid)))
    except (ValueError, TypeError):
        return None


def _layer(db, fn: str, oid) -> dict | None:
    """RCM 계층은 표준(baseline)+회사(instance) 합성 — 화면과 같은 resolver 로 회사 기준 코드·이름을 얻는다(활성 테넌트 필요)."""
    from app.services import control_resolver
    sid = str(oid)
    return next((r for r in getattr(control_resolver, fn)(db) if str(r.get("id")) == sid), None)


def _control(db, cid) -> str | None:
    c = _layer(db, "resolve_controls", cid)
    return _j("통제", c.get("code"), _short(c.get("name"))) if c else None


def _user(db, uid) -> str | None:
    from app.models.user import User
    u = _get(db, User, uid)
    return f"{u.display_name}({u.email})" if u else None


def _rcm(kind_ko: str, fn: str) -> Callable:
    def f(db, oid, _p):
        o = _layer(db, fn, oid)
        return _j(kind_ko, o.get("code"), _short(o.get("name") or o.get("description"))) if o else None
    return f


def _risk_category(db, oid, _p):
    from app.models.rcm_baseline import BaselineRiskCategory
    o = _get(db, BaselineRiskCategory, oid)
    return _j("위험 분류", o.code, _short(o.name)) if o else None


def _control_change(db, oid, _p):
    from app.models.control_change import ControlChange
    o = _get(db, ControlChange, oid)
    return _j("통제", o.control_code, _short(o.control_name)) if o else None


def _change_batch(db, oid, _p):
    from app.models.control_change import ControlChangeBatch
    o = _get(db, ControlChangeBatch, oid)
    return f"일괄 상신 {o.item_count}건" if o else None


def _scoping(db, oid, _p):
    from app.models.scoping import Scoping
    o = _get(db, Scoping, oid)
    return f"{o.fiscal_year} 회계연도 스코핑" if o else None


def _rcm_year(db, oid, _p):
    from app.models.rcm_governance import RcmFiscalYear
    o = _get(db, RcmFiscalYear, oid)
    return f"{o.fiscal_year} 회계연도 RCM" if o else None


def _scoping_account(db, oid, _p):
    from app.models.scoping import ScopingAccount
    o = _get(db, ScopingAccount, oid)
    return _j("계정", o.name) if o else None


def _fs(db, oid, _p):
    from app.models.financial_statement import FS_STATEMENT_LABELS, FsStatement
    o = _get(db, FsStatement, oid)
    return f"{o.fiscal_year} 회계연도 {FS_STATEMENT_LABELS.get(o.statement_type, o.statement_type)}" if o else None


def _named(kind_ko: str, model_path: str, attr: str = "name") -> Callable:
    def f(db, oid, _p):
        mod, cls = model_path.rsplit(".", 1)
        model = getattr(__import__(mod, fromlist=[cls]), cls)
        o = _get(db, model, oid)
        return _j(kind_ko, _short(getattr(o, attr, None), 60)) if o else None
    return f


def _by_control(kind_ko: str, model_path: str) -> Callable:
    """통제에 딸린 행(테스트·평가·위험평가 등) — '테스트 · 통제 EL-010 …'"""
    def f(db, oid, _p):
        mod, cls = model_path.rsplit(".", 1)
        model = getattr(__import__(mod, fromlist=[cls]), cls)
        o = _get(db, model, oid)
        if not o:
            return None
        fy = getattr(o, "fiscal_year", None)
        return _j(kind_ko, f"({fy})" if fy else None, "·", _control(db, o.control_id) or "")
    return f


def _test_step(db, oid, p):
    from app.models.test_module import TestStep
    o = _get(db, TestStep, oid)
    return _by_control("테스트 단계", "app.models.test_module.TestRun")(db, o.test_run_id, p) if o else None


def _deficiency(db, oid, _p):
    from app.models.remediation import Deficiency
    o = _get(db, Deficiency, oid)
    return _j("미비점", o.code, _short(o.description, 30)) if o else None


def _plan(db, oid, p):
    from app.models.remediation import RemediationPlan
    o = _get(db, RemediationPlan, oid)
    return _j("개선계획 ·", _deficiency(db, o.deficiency_id, p)) if o else None


def _evidence_link(db, oid, p):
    from app.models.evidence import EvidenceLink
    o = _get(db, EvidenceLink, oid)
    return _named("증빙", "app.models.evidence.EvidenceFile", "filename")(db, o.file_id, p) if o else None


def _control_assertion(db, oid, _p):
    from app.services import control_resolver
    sid = str(oid)
    o = next((r for r in control_resolver.resolve_control_assertion_links(db) if str(r.get("id")) == sid), None)
    return _control(db, o.get("control_id")) if o else None


def _department(db, oid, _p):
    from app.models.org import Department
    o = _get(db, Department, oid)
    return _j("부서", o.name) if o else None


def _membership(db, oid, p):
    from app.models.org import UserDepartment
    o = _get(db, UserDepartment, oid)
    return _j(_user(db, o.user_id), "→", _department(db, o.department_id, p)) if o else None


def _assignment(db, oid, p):
    from app.models.role_assignment import RoleAssignment
    o = _get(db, RoleAssignment, oid)
    if not o:
        return None
    tgt = (_control(db, o.target_id) if o.scope == "control"
           else _rcm("프로세스", "resolve_processes")(db, o.target_id, p))
    return _j(_user(db, o.user_id), "·", o.role_name, ("· " + tgt) if tgt else None)


def _cycle(db, oid, _p):
    from app.models.assessment import AssessmentCycle
    o = _get(db, AssessmentCycle, oid)
    return _j("회차", o.name) if o else None


def _invitation(db, oid, _p):
    from app.models.external import Invitation
    o = _get(db, Invitation, oid)
    return f"초대 {o.display_name}({o.email})" if o else None


def _external_profile(db, oid, _p):
    from app.models.external import ExternalProfile
    o = _get(db, ExternalProfile, oid)
    return _user(db, o.user_id) if o else None


def _control_link(db, oid, _p):
    from app.models.control_link import ControlAccountLink
    o = _get(db, ControlAccountLink, oid)
    return _j("통제", o.control_code, "↔", o.account_name) if o else None


def _schedule_plan(_db, value, _p):
    return f"{value} 회계연도 일정안"


def _schedule_item(db, oid, p):
    from app.models.schedule import ScheduleItem
    o = _get(db, ScheduleItem, oid)
    return _j(f"{p.get('fiscal_year')} 회계연도 일정" if p.get("fiscal_year") else "일정", _short(o.title)) if o else None


def _report_doc(_db, value, p):
    return _j(f"{p.get('fiscal_year')} 회계연도" if p.get("fiscal_year") else None, REPORT_DOCS.get(value, value))


RESOLVERS: dict[str, Callable] = {
    "control": lambda db, oid, _p: _control(db, oid),
    "process": _rcm("프로세스", "resolve_processes"),
    "sub_process": _rcm("하위 프로세스", "resolve_sub_processes"),
    "risk": _rcm("위험", "resolve_risks"),
    "risk_category": _risk_category,
    "control_assertion": _control_assertion,
    "control_change": _control_change,
    "change_batch": _change_batch,
    "scoping": _scoping,
    "scoping_account": _scoping_account,
    "rcm_year": _rcm_year,
    "fs_statement": _fs,
    "euc": _named("EUC", "app.models.euc.EucFile"),
    "iuc": _named("IUC", "app.models.iuc.InformationItem"),
    "deficiency": _deficiency,
    "plan": _plan,
    "design_assessment": _by_control("설계평가", "app.models.remediation.DesignAssessment"),
    "evidence": _named("증빙", "app.models.evidence.EvidenceFile", "filename"),
    "evidence_link": _evidence_link,
    "user": lambda db, oid, _p: _user(db, oid),
    "department": _department,
    "membership": _membership,
    "assignment": _assignment,
    "cycle": _cycle,
    "activity": _by_control("평가 수행", "app.models.assessment.AssessmentActivity"),
    "rawc": _by_control("통제 위험평가", "app.models.test_module.ControlRiskAssessment"),
    "test_run": _by_control("테스트", "app.models.test_module.TestRun"),
    "test_step": _test_step,
    "control_link": _control_link,
    "invitation": _invitation,
    "external_profile": _external_profile,
    "proposal": _named("제안", "app.models.proposal.Proposal", "title"),
    "schedule_plan": _schedule_plan,
    "schedule_item": _schedule_item,
    "report_doc": _report_doc,
}


def label(db, kind: str | None, value, params: dict) -> str | None:
    if not kind or value in (None, ""):
        return None
    f = RESOLVERS.get(kind)
    out = f(db, value, params) if f else None
    return out[:300] if out else None


def summarize(payload) -> str | None:
    """일괄 처리 응답 → '처리 12건 · 제외 2건'. 모르는 모양이면 None."""
    if isinstance(payload, list):
        return f"{len(payload)}건"
    if not isinstance(payload, dict):
        return None
    if isinstance(payload.get("summary_text"), str):   # 엑셀 갱신 반영 — "통제 61건 변경"(13.9-109)
        return payload["summary_text"]
    parts = []
    for key, name in (("ok", "처리"), ("updated_count", "반영"), ("deleted_count", "삭제"), ("item_count", "상신"),
                      ("created", "등록"), ("updated", "수정"), ("assigned", "배정"), ("removed", "해제"),
                      ("matched", "매칭"), ("applied", "반영"), ("rejected", "반려"), ("failed", "실패"), ("skipped_ids", "제외"), ("skipped", "제외")):
        v = payload.get(key)
        n = len(v) if isinstance(v, list | dict) else v if isinstance(v, int) and not isinstance(v, bool) else None
        if n is not None:
            parts.append(f"{name} {n}건")
    return " · ".join(parts) or None
