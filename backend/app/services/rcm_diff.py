"""RCM 확정본 비교 (ADR-0038 2-5 후속, 2026-10-08) — 스냅샷 두 개(또는 스냅샷 ↔ 현재 RCM)의 차이. 순수 함수.

- 같은 항목은 `id` 로 맞춘다 — 회사별 수정(override)이 있어도 id 는 그대로라, 코드가 바뀌어도 "코드 변경"으로 잡힌다.
- 시스템 칸(id·출처·생성/수정 시각·override 여부)은 비교하지 않는다 — 사람이 보는 내용만.
- 상위 연결(`risk_id` 등)은 id 대신 그 스냅샷 안의 **코드**로 바꿔 비교한다(읽을 수 있게).
- 어서션은 순서와 무관하게 집합으로 비교한다.
"""
from __future__ import annotations

LAYERS = ("processes", "sub_processes", "risks", "controls")
LAYER_LABELS = {"processes": "프로세스", "sub_processes": "하위프로세스", "risks": "위험", "controls": "통제"}
SKIP = {"id", "source", "baseline_id", "is_overridden", "created_at", "updated_at"}

FIELD_LABELS = {
    "code": "코드", "name": "이름", "description": "설명", "objective": "통제 목적", "owner_name": "통제 담당자",
    "is_key_control": "핵심통제", "preventive_detective": "예방/적발", "auto_manual": "자동/수동",
    "activity_approval": "활동: 승인", "activity_verification": "활동: 검증", "activity_physical": "활동: 물리적",
    "activity_master_data": "활동: 마스터데이터", "activity_reconciliation": "활동: 대사", "activity_supervision": "활동: 감독",
    "related_accounts": "관련 계정", "frequency": "수행 주기", "assessment_frequency": "평가 주기",
    "ipe_relevant": "IPE 관련", "related_systems": "관련 시스템", "euc_description": "EUC",
    "risk": "위험", "risk_level": "위험 수준", "sub_process_code": "하위프로세스", "process_code": "프로세스",
    "assertions": "어서션", "assessment_level": "평가 수준", "process": "프로세스", "sub_process": "하위프로세스",
}
# 상위 연결 칸 → (비교에 쓸 이름, 부모 계층)
PARENT_REFS = {"process_id": ("process", "processes"), "sub_process_id": ("sub_process", "sub_processes"),
               "risk_id": ("risk", "risks")}


def _title(layer: str, row: dict) -> str:
    t = row.get("name") or row.get("description") or ""
    return t if len(t) <= 60 else t[:57] + "…"


def _normalize(snapshot: dict) -> dict[str, dict[str, dict]]:
    """계층별 {id: 비교용 칸들}. 상위 연결은 코드로, 어서션은 정렬된 목록으로."""
    codes = {layer: {str(r["id"]): r.get("code") for r in snapshot.get(layer, [])} for layer in LAYERS}
    out: dict[str, dict[str, dict]] = {}
    for layer in LAYERS:
        rows = {}
        for r in snapshot.get(layer, []):
            v = {}
            for k, val in r.items():
                if k in SKIP:
                    continue
                if k in PARENT_REFS:
                    name, parent = PARENT_REFS[k]
                    v[name] = codes[parent].get(str(val)) if val is not None else None
                elif k == "assertions":
                    v[k] = sorted(val or [])
                else:
                    v[k] = val
            rows[str(r["id"])] = v
        out[layer] = rows
    return out


def _fmt(v):
    if isinstance(v, list):
        return ", ".join(str(x) for x in v) if v else ""
    return v


def diff(base: dict, target: dict) -> dict:
    """base → target 에서 무엇이 추가·삭제·변경됐는가. 계층별 목록과 건수 요약."""
    a, b = _normalize(base), _normalize(target)
    layers, summary = {}, {}
    for layer in LAYERS:
        ra, rb = a[layer], b[layer]
        added = [{"id": i, "code": rb[i].get("code"), "title": _title(layer, rb[i])} for i in rb if i not in ra]
        removed = [{"id": i, "code": ra[i].get("code"), "title": _title(layer, ra[i])} for i in ra if i not in rb]
        changed = []
        for i in ra:
            if i not in rb:
                continue
            fields = []
            for k in sorted(set(ra[i]) | set(rb[i]), key=lambda x: list(FIELD_LABELS).index(x) if x in FIELD_LABELS else 999):
                before, after = ra[i].get(k), rb[i].get(k)
                if before == after:
                    continue
                f = {"field": k, "label": FIELD_LABELS.get(k, k), "before": _fmt(before), "after": _fmt(after)}
                if k == "assertions":
                    f["added"] = sorted(set(after or []) - set(before or []))
                    f["removed"] = sorted(set(before or []) - set(after or []))
                fields.append(f)
            if fields:
                changed.append({"id": i, "code": rb[i].get("code"), "title": _title(layer, rb[i]), "changes": fields})
        key = lambda x: x["code"] or ""  # noqa: E731
        layers[layer] = {"added": sorted(added, key=key), "removed": sorted(removed, key=key),
                         "changed": sorted(changed, key=key)}
        summary[layer] = {"added": len(added), "removed": len(removed), "changed": len(changed)}
    total = sum(v for s in summary.values() for v in s.values())
    return {"summary": summary, "total": total, "layers": layers}


def summary_text(d: dict) -> str:
    """"통제 3건 변경·1건 추가, 위험 1건 삭제" — 결재 패널용 한 줄. 변경이 없으면 '변경 없음'."""
    parts = []
    for layer in ("controls", "risks", "sub_processes", "processes"):
        s = d["summary"][layer]
        bits = [f"{s['changed']}건 변경" if s["changed"] else "", f"{s['added']}건 추가" if s["added"] else "",
                f"{s['removed']}건 삭제" if s["removed"] else ""]
        bits = [x for x in bits if x]
        if bits:
            parts.append(f"{LAYER_LABELS[layer]} " + "·".join(bits))
    return ", ".join(parts) if parts else "변경 없음"
