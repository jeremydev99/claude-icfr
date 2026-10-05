"""스코핑 유의 계정 ↔ RCM 통제 커버리지 (초안, 2026-10-03) — 이름 대조 규칙과 집계."""
from types import SimpleNamespace

from app.services import scoping_coverage as sc


def test_norm_strips_note_numbering_spaces_and_suffix() -> None:
    assert sc.norm("NOTE 34. 금융위험 관리") == "금융위험관리"
    assert sc.norm("29. 법인세") == "법인세"
    assert sc.norm("금융위험관리 주석") == "금융위험관리"
    assert sc.norm("충당부채(장기근속급여)") == "충당부채(장기근속급여)"
    assert sc.norm("판매관리비") == "판매비와관리비"  # 동의어


def test_split_tokens_drops_na_and_splits_separators() -> None:
    assert sc.split_tokens("N/A") == []
    assert sc.split_tokens("매출, 매출채권/계약자산\n복리후생비,경상연구개발비") == [
        "매출액", "매출채권", "계약자산", "복리후생비", "경상연구개발비"]
    assert sc.split_tokens(None) == []


def test_match_kind_exact_partial_and_short_token_rule() -> None:
    assert sc.match_kind("현금 성자산", "현금성자산") == "exact"
    assert sc.match_kind("현금및현금성자산", "현금성자산") == "partial"
    # 2자 토큰은 부분 일치로 잡지 않는다(매출원가·매출채권 오탐 방지)
    assert sc.match_kind("매출원가", "원가") is None
    assert sc.match_kind("NOTE 29. 법인세", "법인세비용") == "partial"


def test_coverage_counts_with_fake_data(monkeypatch) -> None:
    s = SimpleNamespace(id="sid", fiscal_year=2026, status="confirmed", confirmed_snapshot={"accounts": {
        "1": {"name": "매출채권", "statement_type": "BS", "final": "Y"},
        "2": {"name": "재고자산", "statement_type": "BS", "final": "Y"},
        "3": {"name": "현금및현금성자산", "statement_type": "BS", "final": "N"},
    }})
    controls = [
        {"code": "C-01", "name": "매출 인식", "is_key_control": True, "related_accounts": "매출, 매출채권, 계약자산"},
        {"code": "C-02", "name": "전사 통제", "is_key_control": False, "related_accounts": "전 계정"},
        {"code": "C-03", "name": "자금", "is_key_control": False, "related_accounts": "현금성자산, 마자급금"},
    ]
    monkeypatch.setattr(sc, "resolve_controls", lambda db: controls)
    monkeypatch.setattr(sc, "_fs_ids", lambda db, s: {})
    monkeypatch.setattr(sc, "_active_links", lambda db: {})
    c = sc.coverage(None, s)
    assert (c["significant_total"], c["covered"], c["uncovered"], c["key_covered"]) == (2, 1, 1, 1)
    assert c["entity_level_controls"] == 1 and c["control_total"] == 3
    by = {r["name"]: r for r in c["accounts"]}
    assert by["매출채권"]["controls"][0]["code"] == "C-01" and by["매출채권"]["controls"][0]["match"] == "exact"
    assert by["재고자산"]["covered"] is False
    # 비유의 계정(현금)은 행에 없지만, 대조 대상 이름에는 포함되어 미대응 토큰으로 잡히지 않는다
    tokens = {u["token"] for u in c["unmatched_rcm_tokens"]}
    assert "현금성자산" not in tokens and "마자급금" in tokens and "계약자산" in tokens
