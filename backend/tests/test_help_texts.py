"""매뉴얼 패널 문구 검증 (7-A, ADR-0035).

**이 파일이 고정하는 것.**
① `menu.*` 키가 `frontend/src/config/navigation.ts` 의 route 와 1:1로 맞는지 —
   route 가 없는 키, 키가 없는 route 가 하나라도 있으면 실패한다. navigation.ts 가
   없으면 skip 하지 않고 실패시킨다(백엔드 전용 실행 환경에서는 절대 이 파일이
   빠지면 안 된다는 뜻).
② 키 형식 위반은 전부 ValueError.
③ 문구가 비어 있는 키(커버리지) 목록.
④ `term.*` 개수가 `ClaudeICFR.md` §11 용어집 항목 수와 같다.
⑤ 조회 API — 접두사 조회(밑줄 이스케이프 포함)·단건 조회·404·401.
⑥ 시드 2회 실행 — 멱등(건수 불변, `created_by` 불변)·소프트 삭제·행위자 `system:seed-help`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — 모든 모델을 Base.metadata 에 등록
from app.core.audit_context import SYSTEM_SEED_HELP
from app.core.help_keys import validate_key
from app.models.base import Base
from app.models.help_text import HelpText
from seeds.seed_help_texts import DATA_FILE, load_entries, seed
from tests.conftest import TestingSessionLocal

REPO_ROOT = Path(__file__).resolve().parents[2]
NAV_PATH = REPO_ROOT / "frontend" / "src" / "config" / "navigation.ts"
ROUTES_PATH = REPO_ROOT / "frontend" / "src" / "routes" / "index.tsx"
CLAUDEICFR_PATH = REPO_ROOT / "ClaudeICFR.md"


# ── 격리 sqlite (다른 테스트의 공유 test.db 를 건드리지 않는다) ─────────

@pytest.fixture()
def iso(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'help.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _entries(*rows: dict) -> list[dict]:
    """load_entries 와 같은 모양의 최소 entry 리스트를 만든다(파일 없이 단위 검증용)."""
    out = []
    for i, r in enumerate(rows):
        out.append({
            "key": r["key"],
            "locale": r.get("locale", "ko"),
            "title": r.get("title"),
            "body": r.get("body"),
            "source": r.get("source"),
            "as_of": r.get("as_of"),
            "baseline_version": r.get("baseline_version", 1),
            "sort_order": r.get("sort_order", i),
        })
    return out


# ── ① menu.* ↔ navigation.ts route 1:1 ──────────────────────

def _nav_routes() -> set[str]:
    assert NAV_PATH.exists(), (
        f"navigation.ts 를 찾지 못했습니다: {NAV_PATH} — 이 테스트는 skip 하지 않는다. "
        "백엔드 전용 체크아웃(예: docker exec 로 컨테이너 안에서 실행)에서는 이 경로가 "
        "보이지 않으므로, 반드시 저장소 전체를 받은 환경에서 pytest 를 돌려야 한다."
    )
    text = NAV_PATH.read_text(encoding="utf-8")
    paths = re.findall(r"path:\s*'([^']+)'", text)
    return {p for p in paths}


def _route_to_menu_key(path: str) -> str:
    return "menu." + path.strip("/").replace("/", ".")


def test_menu_keys_match_navigation_routes():
    expected = {_route_to_menu_key(p) for p in _nav_routes()}
    entries = load_entries(DATA_FILE)
    actual = {e["key"] for e in entries if e["key"].startswith("menu.")}
    missing_in_data = expected - actual
    # 사이드바에 없는 하위 화면(예: /rcm/links, /proposals/:id)도 라우터에 있으면 menu.* 를 둘 수 있다.
    # 패널은 `:id` 같은 id 조각을 떼고 조회한다(help.pure.ts routeSegment).
    router_paths = re.findall(r"path:\s*'([^']+)'",ROUTES_PATH.read_text(encoding="utf-8"))
    sub_routes = {"/".join(seg for seg in p.split("/") if not seg.startswith(":")) for p in router_paths}
    extra_in_data = actual - expected - {_route_to_menu_key(p) for p in sub_routes if p.strip("/")}
    assert not missing_in_data, f"navigation.ts route 인데 menu.* 키가 없음: {sorted(missing_in_data)}"
    assert not extra_in_data, f"menu.* 키인데 navigation.ts route 가 없음: {sorted(extra_in_data)}"


# ── ② 키 형식 ────────────────────────────────────────────────

@pytest.mark.parametrize("bad", [
    "Menu.rcm",          # 대문자
    "menu..rcm",         # 빈 세그먼트
    ".menu.rcm",         # 선행 점
    "menu.rcm.",         # 후행 점
    "menu/rcm",          # 슬래시
    "menu rcm",          # 공백
    "menu.rcm!",         # 허용 외 문자
    "",                  # 빈 문자열
])
def test_validate_key_rejects_bad_format(bad):
    with pytest.raises(ValueError):
        validate_key(bad)


@pytest.mark.parametrize("ok", [
    "menu.rcm",
    "menu.admin.departments",
    "field.rcm.control_type",   # 밑줄 허용(2번 승인)
    "action.rcm-hierarchy.add",
    "term.icfr",
])
def test_validate_key_accepts_approved_charset(ok):
    validate_key(ok)  # 예외 없이 통과


def test_load_entries_rejects_bad_key_format(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text('[{"key": "Menu.Bad", "title": "x", "body": "y"}]', encoding="utf-8")
    with pytest.raises(ValueError):
        load_entries(bad_file)


def test_load_entries_rejects_duplicate_key(tmp_path):
    dup_file = tmp_path / "dup.json"
    dup_file.write_text(
        '[{"key": "menu.a", "body": "1"}, {"key": "menu.a", "body": "2"}]', encoding="utf-8"
    )
    with pytest.raises(ValueError):
        load_entries(dup_file)


def test_load_entries_requires_as_of_when_source_present(tmp_path):
    f = tmp_path / "src.json"
    f.write_text(
        '[{"key": "term.x", "body": "y", "source": "회계감사기준 §1"}]', encoding="utf-8"
    )
    with pytest.raises(ValueError):
        load_entries(f)


def test_load_entries_allows_source_with_as_of(tmp_path):
    f = tmp_path / "src_ok.json"
    f.write_text(
        '[{"key": "term.x", "body": "y", "source": "회계감사기준 §1", "as_of": "2026-01-01"}]',
        encoding="utf-8",
    )
    entries = load_entries(f)
    assert entries[0]["source"] == "회계감사기준 §1"
    assert entries[0]["as_of"].isoformat() == "2026-01-01"


# ── ③ 커버리지(문구 미작성 키) ──────────────────────────────

def test_real_data_file_loads_and_reports_empty_body():
    entries = load_entries(DATA_FILE)
    empty = sorted(e["key"] for e in entries if not e["body"])
    # 6-1 STEP 0 때는 화면이 없는 메뉴 6개를 키만 뒀다. 2026-09-30 초안 화면이 생겨
    # 2026-10-03(7-B) 문구를 채웠다 — 이제 빈 키는 없다. 새로 빈 키를 두면 여기서 드러난다.
    assert empty == []


# ── ④ term.* 개수 == §11 용어집 항목 수 ─────────────────────

def _glossary_row_count() -> int:
    assert CLAUDEICFR_PATH.exists(), f"ClaudeICFR.md 를 찾지 못했습니다: {CLAUDEICFR_PATH}"
    text = CLAUDEICFR_PATH.read_text(encoding="utf-8")
    m = re.search(r"## 11\. 용어집.*?\n(.*?)\n---", text, re.S)
    assert m, "ClaudeICFR.md 에서 §11 용어집 섹션을 찾지 못했습니다"
    rows = [
        line for line in m.group(1).splitlines()
        if line.strip().startswith("|") and "---" not in line and "용어" not in line
    ]
    return len(rows)


def test_term_key_count_matches_glossary():
    entries = load_entries(DATA_FILE)
    term_keys = [e["key"] for e in entries if e["key"].startswith("term.")]
    assert len(term_keys) == _glossary_row_count()


# ── ⑥ 시드 — 멱등·소프트 삭제·행위자 ─────────────────────────

def test_seed_idempotent_twice(iso):
    db = iso()
    entries = _entries({"key": "t.a", "title": "A", "body": "본문 A"})
    r1 = seed(db, entries)
    db.commit()
    assert r1.created == ["t.a"]

    row = db.query(HelpText).filter(HelpText.key == "t.a").one()
    created_by_1 = row.created_by
    assert created_by_1 == SYSTEM_SEED_HELP

    r2 = seed(db, entries)
    db.commit()
    assert r2.created == []
    assert r2.updated == []
    assert r2.unchanged == ["t.a"]
    assert db.query(HelpText).filter(HelpText.key == "t.a").count() == 1

    row2 = db.query(HelpText).filter(HelpText.key == "t.a").one()
    assert row2.created_by == created_by_1


def test_seed_updates_only_changed_fields_and_keeps_created_by(iso):
    db = iso()
    entries = _entries({"key": "t.b", "title": "제목", "body": "본문1"})
    seed(db, entries)
    db.commit()
    created_by_before = db.query(HelpText).filter(HelpText.key == "t.b").one().created_by

    changed = _entries({"key": "t.b", "title": "제목", "body": "본문2"})
    report = seed(db, changed)
    db.commit()
    assert report.updated == ["t.b"]

    row = db.query(HelpText).filter(HelpText.key == "t.b").one()
    assert row.body == "본문2"
    assert row.created_by == created_by_before  # 갱신해도 created_by 는 유지(ADR-0036)


def test_seed_soft_deletes_missing_keys(iso):
    db = iso()
    first = _entries(
        {"key": "t.keep", "body": "유지"},
        {"key": "t.drop", "body": "삭제될 것"},
    )
    seed(db, first)
    db.commit()

    second = _entries({"key": "t.keep", "body": "유지"})
    report = seed(db, second)
    db.commit()

    assert report.deleted == ["t.drop"]
    dropped = db.query(HelpText).filter(HelpText.key == "t.drop").one()
    assert dropped.is_deleted is True
    assert dropped.deleted_by == SYSTEM_SEED_HELP
    assert dropped.deleted_at is not None

    kept = db.query(HelpText).filter(HelpText.key == "t.keep").one()
    assert kept.is_deleted is False


def test_seed_tracks_empty_body_in_report(iso):
    db = iso()
    entries = _entries({"key": "t.empty", "title": None, "body": None})
    report = seed(db, entries)
    db.commit()
    assert report.empty_body == ["t.empty"]


# ── ⑤ 조회 API ───────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def api_fixtures(app):
    """API 테스트용 고정 데이터 — 공유 test.db 에 넣는다(다른 테스트와 키가 겹치지 않게 접두사 분리).

    `app` 에 의존한다 — 그 fixture가 `Base.metadata.create_all` 로 공유 test.db 테이블을
    만든다. 의존하지 않으면 이 fixture가 먼저 실행돼 `help_texts` 테이블이 없는 채로
    insert를 시도해 실패한다.
    """
    db = TestingSessionLocal()
    try:
        entries = _entries(
            {"key": "apitest.parent", "title": "부모", "body": "부모 본문"},
            {"key": "apitest.parent.child", "title": "자식", "body": "자식 본문"},
            {"key": "apitest.empty", "title": None, "body": None},
            # 밑줄 이스케이프 검증용 — "us_er"(밑줄) vs "usxer"(글자, 같은 자리)
            {"key": "us_er.a", "title": "밑줄", "body": "밑줄 본문"},
            {"key": "usxer.a", "title": "글자", "body": "글자 본문"},
        )
        seed(db, entries)
        db.commit()
    finally:
        db.close()


def test_list_help_texts_by_prefix_requires_auth(client: TestClient):
    r = client.get("/api/help", params={"prefix": "apitest"})
    assert r.status_code == 401


def test_list_help_texts_by_prefix(client: TestClient, headers: dict):
    r = client.get("/api/help", params={"prefix": "apitest"}, headers=headers)
    assert r.status_code == 200, r.text
    keys = {row["key"] for row in r.json()}
    assert keys == {"apitest.parent", "apitest.parent.child", "apitest.empty"}


def test_list_help_texts_prefix_underscore_is_escaped(client: TestClient, headers: dict):
    r = client.get("/api/help", params={"prefix": "us_er"}, headers=headers)
    assert r.status_code == 200, r.text
    keys = {row["key"] for row in r.json()}
    assert keys == {"us_er.a"}  # "usxer.a" 가 섞이면 밑줄 이스케이프가 깨진 것


def test_get_help_text_single(client: TestClient, headers: dict):
    r = client.get("/api/help/apitest.parent", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["key"] == "apitest.parent"
    assert body["body"] == "부모 본문"


def test_get_help_text_not_found(client: TestClient, headers: dict):
    r = client.get("/api/help/apitest.does-not-exist", headers=headers)
    assert r.status_code == 404


@pytest.fixture()
def headers(client: TestClient) -> dict:
    r = client.post("/api/auth/login", data={"username": "admin@acme.example", "password": "admin123"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}
