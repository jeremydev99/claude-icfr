"""스코핑 유의 계정 ↔ RCM 통제 커버리지 (초안, 2026-10-03).

재무제표 → 스코핑(8-E)으로 유의한 계정이 정해져도, 그 계정을 다루는 통제가 RCM 에 있는지 볼 방법이
없었다. RCM 의 `related_accounts` 는 "매출, 매출채권, 계약자산" 같은 **자유 텍스트**라 구조화된 연결이
없다 — 그래서 **이름 대조로 추정**한다. 확정 판정이 아니라 검토 출발점이다(화면도 "추정"으로 표시).

대조 규칙(`match_kind`):
- `exact` — 공백·괄호 표기를 걷어낸 이름이 같다 (`현금성자산` = `현금 성자산`)
- `partial` — 한쪽이 다른 쪽을 포함하고 짧은 쪽이 3자 이상 (`현금성자산` ⊂ `현금및현금성자산`).
  2자 토큰(`매출`)은 `매출원가`·`매출채권`까지 잡아 오탐이 많아 부분 일치에서 뺀다.
- `전 계정`·`전계정` 토큰은 **전사 통제**로 따로 센다(특정 계정 커버로 보지 않는다).
- `N/A` 는 무시한다. `…주석` 토큰은 끝의 `주석`을 떼고 주석 계정(`NOTE 34. 금융위험 관리`)과 대조한다.

저장하지 않는다. 확정된 스코핑은 확정 스냅샷의 결론을 쓴다(화면·대시보드와 같은 기준).
"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models.scoping import STATUS_CONFIRMED, Scoping
from app.services import scoping as svc
from app.services.control_resolver import resolve_controls

ALL_ACCOUNTS_TOKENS = {"전계정", "모든계정"}
_IGNORE = {"n/a", "na", "-", "해당없음"}
# 같은 계정을 다르게 부르는 표기 — 실제 RCM·재무제표 대조에서 나온 것만 넣는다(정규화 후 값 → 대표 표기)
SYNONYMS = {
    "우발부채및약정사항": "우발채무및약정사항",
    "판매관리비": "판매비와관리비",
    "매출": "매출액",
    "부가세예수금": "부가가치세예수금",
}


def norm(name: str | None) -> str:
    """대조용 정규화 — 주석 번호(`NOTE 29.`·`29.`) 접두어와 끝의 `주석`을 떼고, 공백 제거·소문자.
    괄호 안 보충 설명은 남긴다(`충당부채(장기근속급여)`)."""
    t = re.sub(r"^\s*(note\s*)?\d+\s*[.)]\s*", "", (name or "").strip(), flags=re.IGNORECASE)
    t = re.sub(r"\s+", "", t).lower()
    t = t[:-2] if t.endswith("주석") and len(t) > 2 else t
    return SYNONYMS.get(t, t)


def split_tokens(text: str | None) -> list[str]:
    """`related_accounts` → 정규화 토큰 목록. 쉼표·슬래시·줄바꿈·가운뎃점으로 나눈다(`N/A` 는 먼저 지운다)."""
    text = re.sub(r"\bn\s*/\s*a\b", "", text or "", flags=re.IGNORECASE)
    out = []
    for raw in re.split(r"[,/\n;·、]", text):
        t = norm(raw)
        if t and t not in _IGNORE:
            out.append(t)
    return out


def match_kind(account_name: str, token: str) -> str | None:
    a, t = norm(account_name), token
    if not a or not t:
        return None
    if a == t:
        return "exact"
    short = min(len(a), len(t))
    if short >= 3 and (t in a or a in t):
        return "partial"
    return None


def coverage(db: Session, s: Scoping) -> dict:
    """유의 계정(최종 결론 Y)별 대응 통제 + 전사 통제 수 + 미대응 계정."""
    if s.status == STATUS_CONFIRMED and s.confirmed_snapshot:
        accounts = [(v["name"], v["statement_type"], v["final"])
                    for v in s.confirmed_snapshot.get("accounts", {}).values()]
    else:
        ev = svc.evaluate(db, s)
        accounts = [(r["account"].name, r["account"].statement_type, r["final"]) for r in ev["accounts"]]

    controls = resolve_controls(db)
    parsed = [(c, split_tokens(c.get("related_accounts"))) for c in controls]
    entity_level = [c for c, toks in parsed if any(t in ALL_ACCOUNTS_TOKENS for t in toks)]

    rows = []
    for name, stype, final in accounts:
        if final != "Y":
            continue
        matched = []
        for c, toks in parsed:
            kinds = [k for k in (match_kind(name, t) for t in toks if t not in ALL_ACCOUNTS_TOKENS) if k]
            if kinds:
                matched.append({
                    "code": c.get("code"), "name": c.get("name"),
                    "is_key_control": bool(c.get("is_key_control")),
                    "match": "exact" if "exact" in kinds else "partial",
                })
        matched.sort(key=lambda m: (m["match"] != "exact", m["code"] or ""))
        rows.append({"name": name, "statement_type": stype, "controls": matched,
                     "covered": bool(matched), "key_covered": any(m["is_key_control"] for m in matched)})

    # RCM 에는 있는데 스코핑 계정 어디에도 안 맞는 토큰 — 이름이 다르거나(오타 포함) 스코핑에 없는 계정
    names = [n for n, _, _ in accounts]
    unknown: dict[str, list[str]] = {}
    for c, toks in parsed:
        for t in toks:
            if t in ALL_ACCOUNTS_TOKENS:
                continue
            if not any(match_kind(n, t) for n in names):
                unknown.setdefault(t, []).append(c.get("code") or "")

    total = len(rows)
    covered = sum(1 for r in rows if r["covered"])
    return {
        "scoping_id": s.id, "fiscal_year": s.fiscal_year, "status": s.status,
        "significant_total": total, "covered": covered, "uncovered": total - covered,
        "key_covered": sum(1 for r in rows if r["key_covered"]),
        "control_total": len(controls), "entity_level_controls": len(entity_level),
        "accounts": rows,
        "unmatched_rcm_tokens": [{"token": t, "control_codes": sorted(set(c))} for t, c in sorted(unknown.items())],
    }
