"""RCM 확정본 비교 (2026-10-08) — 순수 비교 함수 + 비교 API·결재 패널 요약."""
from fastapi.testclient import TestClient

from app.services.rcm_diff import diff, summary_text
from tests.test_governance import T
from tests.test_rcm_approval import Y, _confirm, _control, _start

P1, SP1, R1, R2 = "p1", "sp1", "r1", "r2"


def _snap(controls, risks=None):
    return {"processes": [{"id": P1, "code": "P", "name": "프로세스", "created_at": "x"}],
            "sub_processes": [{"id": SP1, "code": "SP", "name": "하위", "process_id": P1}],
            "risks": risks or [{"id": R1, "code": "R-1", "description": "위험1", "sub_process_id": SP1},
                               {"id": R2, "code": "R-2", "description": "위험2", "sub_process_id": SP1}],
            "controls": controls}


def _c(i, **kw):
    return {"id": i, "code": f"C-{i}", "name": f"통제{i}", "risk_id": R1, "assertions": ["E", "C"],
            "owner_name": "김담당", "updated_at": "t1", "source": "baseline", "is_overridden": False, **kw}


def test_diff_added_removed_changed_and_ignores_system_fields() -> None:
    a = _snap([_c("1"), _c("2"), _c("3")])
    b = _snap([_c("1", updated_at="t2", is_overridden=True),                      # 시스템 칸만 바뀜 → 변경 아님
               _c("2", owner_name="이담당", risk_id=R2, assertions=["C", "V"]),   # 담당자·위험·어서션 변경
               _c("4")])                                                           # 3 삭제, 4 추가
    d = diff(a, b)
    s = d["summary"]["controls"]
    assert (s["added"], s["removed"], s["changed"]) == (1, 1, 1)
    ch = {f["field"]: f for f in d["layers"]["controls"]["changed"][0]["changes"]}
    assert set(ch) == {"owner_name", "risk", "assertions"}
    assert (ch["risk"]["before"], ch["risk"]["after"]) == ("R-1", "R-2")              # id 가 아니라 코드로
    assert (ch["assertions"]["added"], ch["assertions"]["removed"]) == (["V"], ["E"])
    assert ch["owner_name"]["label"] == "통제 담당자"
    assert summary_text(d) == "통제 1건 변경·1건 추가·1건 삭제"


def test_diff_same_order_insensitive_assertions_is_no_change() -> None:
    a = _snap([_c("1", assertions=["E", "C"])])
    b = _snap([_c("1", assertions=["C", "E"])])
    assert diff(a, b)["total"] == 0 and summary_text(diff(a, b)) == "변경 없음"


def test_compare_api_and_review_summary(client: TestClient) -> None:
    t = T(client, {"lead": ("icfr_lead",), "master": ("icfr_manager",)})
    cid = _control(t)
    rid = _start(client, t)
    _confirm(client, t, rid)
    r = client.get(f"{Y}/compare", headers=t.h["lead"], params={"base": f"{rid}:1", "target": "live"}).json()
    assert r["total"] == 0 and r["base"] == "2026 회계연도 RCM v1" and r["target"] == "현재 RCM"
    # 재오픈 → 수정 → 검토 요청: 결재 패널에 직전 확정본 대비 요약
    req = client.post(f"{Y}/{rid}/reopen-requests", headers=t.h["lead"], json={"reason": "변경"}).json()
    client.post(f"{Y}/{rid}/reopen-requests/{req['governance']['pending_reopen']['id']}/decide",
                headers=t.h["master"], json={"approve": True})
    assert client.patch(f"/api/rcm/controls/{cid}", headers=t.h["master"], json={"name": "바뀐 통제"}).status_code == 200
    r = client.get(f"{Y}/compare", headers=t.h["lead"], params={"base": f"{rid}:1"}).json()
    ch = r["layers"]["controls"]["changed"][0]["changes"]
    assert [(c["field"], c["before"], c["after"]) for c in ch] == [("name", "통제", "바뀐 통제")]
    assert client.post(f"{Y}/{rid}/transition", headers=t.h["lead"], json={"to_status": "review"}).status_code == 200
    d = client.get(f"{Y}/{rid}", headers=t.h["master"]).json()
    assert d["diff_summary"] == "직전 확정본(v1) 대비 통제 1건 변경"
    assert client.get(f"{Y}/compare", headers=t.h["lead"], params={"base": "x"}).status_code == 422
    assert client.get(f"{Y}/compare", headers=t.h["lead"], params={"base": f"{rid}:9"}).status_code == 404


def test_coded_values_shown_in_korean() -> None:
    """결재자가 코드 대신 한글 값을 본다(2026-10-14)."""
    from app.services.rcm_diff import _fmt
    assert (_fmt("quarterly", "assessment_frequency"), _fmt("annual", "assessment_frequency")) == ("분기", "연")
    assert _fmt("Q", "frequency") == "분기" and _fmt("MR", "risk_level") == "보통"
    assert _fmt(True, "is_key_control") == "예" and _fmt("자유 문장", "description") == "자유 문장"


def test_backfilled_control_status_not_compared_against_older_snapshot() -> None:
    """통제현황(13.9-134)은 확정 뒤 원본에서 보강 적재했다 — 키가 없는 옛 확정본과는 비교하지 않는다.
    양쪽 모두 키가 있으면(이후 판끼리) 변경으로 잡는다."""
    old = _snap([_c("1")])                                          # v4 — 키 없음
    now = _snap([_c("1", control_status="1. 윤리헌장 게시")])
    assert diff(old, now)["total"] == 0
    later = _snap([_c("1", control_status="1. 윤리헌장 게시 + 서약서")])
    ch = diff(now, later)["layers"]["controls"]["changed"][0]["changes"]
    assert [(f["field"], f["label"]) for f in ch] == [("control_status", "통제현황")]
    # 다른 칸은 종전대로 — 옛 판에 키가 없어도 변경으로 잡는다
    assert diff(old, _snap([_c("1", population="전표")]))["total"] == 1
