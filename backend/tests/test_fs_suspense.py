"""임시계정(원본 차이) — 흡수·확정 차단·해소 (ADR-0037 §2.13, 마스터 지시 2026-09-30).

사례는 실측 결함을 재현한다: 정산표 `지배주주지분` 수식이 자본조정을 빠뜨림(8-B 합성 워크북 `horizontal_bs`),
정산표 COA 합과 공시 행 금액이 1 어긋남(8-B2 `worksheet_bs`).
"""
from decimal import Decimal

from fastapi.testclient import TestClient

from tests.test_fs_upload import (
    _attach,
    _disclosure_2y,
    _post,
    _reopen,
    _tenant,
    horizontal_bs,
    worksheet_bs,
)

D = Decimal
PARENT = "지배주주의소유주에게귀속되는지분"


def _stale(client) -> tuple[dict, str]:
    """지배주주지분 500(자본조정 −100 누락) — (헤더, 2025 재무제표 id)."""
    h, _ = _tenant(client)
    r = _post(client, h, horizontal_bs(stale_parent=True), mode="commit", unit=1)
    assert r.status_code == 200, r.text
    return h, next(s["statement_id"] for s in r.json()["statements"] if s["fiscal_year"] == 2025)


def _items(client, h, sid) -> dict[str, dict]:
    r = client.get(f"/api/fs/statements/{sid}/suspense", headers=h)
    assert r.status_code == 200, r.text
    return {x["parent_name"]: x for x in r.json() if not x["is_deleted"]}


def _resolve(client, h, sid, amount_id, **body):
    return client.post(f"/api/fs/statements/{sid}/suspense/{amount_id}/resolve", headers=h, json=body)


def _find(nodes, name):
    for n in nodes:
        if n["name"] == name:
            return n
        got = _find(n["children"], name)
        if got:
            return got
    return None


def test_absorb_blocks_finalize_and_numbers_stay_original(client: TestClient) -> None:
    h, sid = _stale(client)
    it = _items(client, h, sid)
    assert {k: D(v["amount"]) for k, v in it.items()} == {PARENT: D(100), "자본총계": D(-100)}
    assert (D(it[PARENT]["actual"]), D(it[PARENT]["expected"])) == (D(500), D(400))
    d = client.get(f"/api/fs/statements/{sid}", headers=h).json()
    assert D(_find(d["tree"], PARENT)["amount"]) == D(500)                     # 원본 숫자는 그대로
    r = client.post(f"/api/fs/statements/{sid}/finalize", headers=h, json={})
    assert r.status_code == 422
    assert {e["rule"] for e in r.json()["detail"]["validation"]["errors"]} == {"suspense_unresolved"}


def test_fix_subtotal_rebalances_chained_difference(client: TestClient) -> None:
    """지배주주지분을 하위 합으로 정정하면 자본총계 아래 −차액도 재계산으로 사라진다."""
    h, sid = _stale(client)
    it = _items(client, h, sid)
    r = _resolve(client, h, sid, it[PARENT]["amount_id"], action="fix_subtotal",
                 reason="정산표 수식이 자본조정·기타포괄을 빠뜨림")
    assert r.status_code == 200, r.text
    assert r.json()["validation"]["ok"], r.json()["validation"]["errors"]
    assert _items(client, h, sid) == {}                                         # 남은 미해결 없음
    parent = _find(r.json()["tree"], PARENT)
    assert D(parent["amount"]) == D(400) and D(parent["raw_meta"]["corrected_from"]) == D(500)
    history = [x for x in client.get(f"/api/fs/statements/{sid}/suspense", headers=h).json() if x["is_deleted"]]
    assert [x["resolved"]["action"] for x in history] == ["fix_subtotal"]
    assert client.post(f"/api/fs/statements/{sid}/finalize", headers=h, json={}).status_code == 200


def test_accept_keeps_difference_with_reason(client: TestClient) -> None:
    h, sid = _stale(client)
    it = _items(client, h, sid)
    for name in (PARENT, "자본총계"):
        r = _resolve(client, h, sid, it[name]["amount_id"], action="accept", reason="원본대로 유지 — 감사인 협의")
        assert r.status_code == 200, r.text
    assert r.json()["validation"]["ok"]
    kept = _items(client, h, sid)
    assert kept["자본총계"]["resolved"]["action"] == "accept" and D(kept["자본총계"]["amount"]) == D(-100)
    assert _resolve(client, h, sid, it["자본총계"]["amount_id"], action="accept", reason="다시").status_code == 409


def test_reclass_moves_difference_to_sibling(client: TestClient) -> None:
    """정산표 외상매출금 131(공시 매출채권 200 보다 1 많음) → 차액 −1 을 외상매출금으로 옮긴다."""
    h, _ = _tenant(client)
    sids = _disclosure_2y(client, h)
    _reopen(client, h, sids[2025])
    r = _attach(client, h, worksheet_bs(over={"외상매출금": {2025: 131}}), mode="commit", unit=1)
    assert r.status_code == 200, r.text
    sid = sids[2025]
    it = _items(client, h, sid)["매출채권"]
    d = client.get(f"/api/fs/statements/{sid}", headers=h).json()
    target = next(c for c in _find(d["tree"], "매출채권")["children"] if c["name"] == "외상매출금")
    other = _find(d["tree"], "현금및현금성자산")

    bad = _resolve(client, h, sid, it["amount_id"], action="reclass", reason="x", target_account_id=other["id"])
    assert bad.status_code == 422 and "같은 소계" in bad.json()["detail"]
    assert _resolve(client, h, sid, it["amount_id"], action="reclass", reason="x").status_code == 422
    ok = _resolve(client, h, sid, it["amount_id"], action="reclass", reason="정산표 입력 오류 1원",
                  target_account_id=target["id"])
    assert ok.status_code == 200, ok.text
    assert ok.json()["validation"]["ok"], ok.json()["validation"]["errors"]
    moved = next(c for c in _find(ok.json()["tree"], "매출채권")["children"] if c["name"] == "외상매출금")
    assert D(moved["amount"]) == D(130) and D(moved["raw_meta"]["reclassed_from"]) == D(131)


def test_resolve_guards(client: TestClient) -> None:
    h, sid = _stale(client)
    aid = _items(client, h, sid)["자본총계"]["amount_id"]
    assert _resolve(client, h, sid, aid, action="accept", reason="  ").status_code == 422
    assert _resolve(client, h, sid, aid, action="delete", reason="x").status_code == 422
    assert _resolve(client, h, sid, "00000000-0000-0000-0000-000000000001", action="accept",
                    reason="x").status_code == 404
    viewer, _ = _tenant(client, roles=("external_auditor",))
    assert _resolve(client, viewer, sid, aid, action="accept", reason="x").status_code == 403
    assert client.get(f"/api/fs/statements/{sid}/suspense", headers=viewer).status_code == 404   # 다른 테넌트

    # 확정 상태에서는 해소하지 않는다 — 모두 accept 로 확정한 뒤 재오픈 없이 시도
    for x in _items(client, h, sid).values():
        assert _resolve(client, h, sid, x["amount_id"], action="accept", reason="유지").status_code == 200
    assert client.post(f"/api/fs/statements/{sid}/finalize", headers=h, json={}).status_code == 200
    assert _resolve(client, h, sid, aid, action="fix_subtotal", reason="x").status_code == 409
