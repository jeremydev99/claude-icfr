"""RCM 엑셀 갱신 업로드 — 엑셀 ↔ 현재 RCM 을 코드로 맞춰 '적용 후 모습'과 할 일을 만든다. 순수 함수.

(2026-10-08, Regina 결정 — 13.9-109 STEP 0 Q1~Q4 추천안)
- 코드가 같으면 같은 항목. 엑셀에 있는 칸만 비교한다(평가 주기 등 엑셀에 없는 칸은 건드리지 않는다).
- 엑셀에 **없는** 기존 항목은 지우지 않고 `missing` 으로만 알린다(Q1 — 일부만 올려 대량 삭제되는 사고 방지).
- 엑셀의 **새 코드**는 회사 추가(add)로 계획한다(Q2).
- 기존 항목의 **상위가 바뀐 경우**는 반영하지 않고 `warnings` 로 알린다(Q3 — 수정 로직이 상위 변경을 지원하지 않는다).
- 미리보기 차이는 `rcm_diff.diff(현재, 적용 후)` 그대로 — 확정본 비교 화면과 같은 모양.
"""
from __future__ import annotations

import copy

from app.services import rcm_diff

# 엑셀에서 오는 통제 칸 (평가 주기 assessment_frequency 는 엑셀에 없다)
CONTROL_FIELDS = (
    "name", "description", "objective", "owner_name",
    "is_key_control", "preventive_detective", "auto_manual",
    "activity_approval", "activity_verification", "activity_physical",
    "activity_master_data", "activity_reconciliation", "activity_supervision",
    "related_accounts", "frequency", "ipe_relevant", "related_systems", "euc_description",
)
LAYER_LABEL = rcm_diff.LAYER_LABELS


def _blank(v):
    return None if v == "" else v


def _same(a, b) -> bool:
    return _blank(a) == _blank(b)


def plan(live: dict, parsed, known_assertions: set[str]) -> dict:
    """live = {processes, sub_processes, risks, controls} (resolver 결과), parsed = `_ParsedRCM`.

    반환: {"target": 적용 후 스냅샷, "ops": 할 일 목록, "missing": 계층별 엑셀에 없는 코드,
          "warnings": 반영하지 않는 것}. ops 는 상위 → 하위 순서(추가된 상위를 하위가 참조).
    """
    target = {k: copy.deepcopy(live.get(k, [])) for k in ("processes", "sub_processes", "risks", "controls")}
    by_code = {k: {r["code"]: r for r in target[k]} for k in target}
    code_of = {k: {str(r["id"]): r["code"] for r in target[k]} for k in target}
    ops: list[dict] = []
    warnings: list[str] = []

    def update(layer, row, changes):
        if changes:
            row.update(changes)
            ops.append({"op": "update", "layer": layer, "id": row["id"], "code": row["code"], "changes": changes})

    def add(layer, code, data, parent_code=None):
        row = {"id": f"new:{layer}:{code}", "code": code, **data}
        target[layer].append(row)
        by_code[layer][code] = row
        code_of[layer][row["id"]] = code
        ops.append({"op": "add", "layer": layer, "code": code, "data": data, "parent_code": parent_code})
        return row

    def parent_id(layer, code):
        r = by_code[layer].get(code)
        return r["id"] if r else None

    def check_parent(layer, row, parent_layer, parent_attr, want_code):
        have = code_of[parent_layer].get(str(row.get(parent_attr)))
        if want_code and have != want_code:
            warnings.append(f"{LAYER_LABEL[layer]} {row['code']}: 상위가 {have} → {want_code} 로 바뀌었지만 반영하지 않습니다"
                            " — 계층 관리에서 옮기세요")

    # 프로세스
    for code, name in parsed.processes.items():
        name = _blank(name)
        row = by_code["processes"].get(code)
        if row is None:
            add("processes", code, {"name": name or code})
        elif name and not _same(row.get("name"), name):
            update("processes", row, {"name": name})

    # 하위프로세스
    for code, info in parsed.sub_processes.items():
        name = _blank(info.get("name"))
        row = by_code["sub_processes"].get(code)
        if row is None:
            add("sub_processes", code, {"name": name or code, "process_id": parent_id("processes", info["process_code"])},
                parent_code=info["process_code"])
            continue
        check_parent("sub_processes", row, "processes", "process_id", info["process_code"])
        if name and not _same(row.get("name"), name):
            update("sub_processes", row, {"name": name})

    # 위험
    for code, info in parsed.risks.items():
        row = by_code["risks"].get(code)
        data = {"description": info["description"], "assessment_level": info["assessment_level"]}
        if row is None:
            add("risks", code, {**data, "sub_process_id": parent_id("sub_processes", info["sub_process_code"])},
                parent_code=info["sub_process_code"])
            continue
        check_parent("risks", row, "sub_processes", "sub_process_id", info["sub_process_code"])
        update("risks", row, {k: v for k, v in data.items() if not _same(row.get(k), v)})

    # 통제
    for c in parsed.controls:
        code = c["code"]
        unknown = sorted(set(c.get("assertions") or []) - known_assertions)
        if unknown:
            warnings.append(f"통제 {code}: 등록되지 않은 어서션 {', '.join(unknown)} 은 반영하지 않습니다")
        want = sorted(set(c.get("assertions") or []) & known_assertions)
        row = by_code["controls"].get(code)
        if row is None:
            data = {f: c.get(f) for f in CONTROL_FIELDS}
            add("controls", code, {**data, "risk_id": parent_id("risks", c["risk_code"]), "assertions": want},
                parent_code=c["risk_code"])
            continue
        check_parent("controls", row, "risks", "risk_id", c["risk_code"])
        update("controls", row, {f: c.get(f) for f in CONTROL_FIELDS if not _same(row.get(f), c.get(f))})
        have = sorted(row.get("assertions") or [])
        if have != want:
            row["assertions"] = want
            ops.append({"op": "assertions", "layer": "controls", "id": row["id"], "code": code,
                        "add": sorted(set(want) - set(have)), "remove": sorted(set(have) - set(want))})

    excel_codes = {"processes": set(parsed.processes), "sub_processes": set(parsed.sub_processes),
                   "risks": set(parsed.risks), "controls": {c["code"] for c in parsed.controls}}
    missing = {k: sorted(r["code"] for r in live.get(k, []) if r["code"] not in excel_codes[k]) for k in excel_codes}
    return {"target": target, "ops": ops, "missing": missing, "warnings": warnings}


def preview(live: dict, parsed, known_assertions: set[str]) -> dict:
    """미리보기 응답 본문 — 확정본 비교와 같은 diff + 엑셀에 없음 + 경고."""
    p = plan(live, parsed, known_assertions)
    d = rcm_diff.diff(live, p["target"])
    return {"diff": d, "summary_text": rcm_diff.summary_text(d), "missing": p["missing"],
            "missing_count": sum(len(v) for v in p["missing"].values()), "warnings": p["warnings"],
            "op_count": len(p["ops"])}
