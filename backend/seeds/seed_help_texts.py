"""매뉴얼 패널 문구 시드 — help_texts (7-A, ADR-0035).

원본은 `backend/seeds/data/help_texts_ko.json` 이다. 이 파일이 콘텐츠의 단일 원천이고,
시드는 그 파일을 읽어 DB 에 멱등 upsert 한다 — 문구 하나를 고치는 데 배포가 필요하지
않게 하려는 것이다(13.9-8). **쓰기 API 는 없다** — 문구 수정은 이 파일을 고치고 시드를
다시 돌리는 것으로 한다(7-C 에서 편집 API 를 검토한다).

실행 (컨테이너 내부, WORKDIR=/app):
    docker compose exec backend python -m seeds.seed_help_texts

**멱등 규칙**:
- 파일에 있고 DB에 없다 → 새로 만든다(`created_by = system:seed-help`)
- 파일에도 DB에도 있다 → **바뀐 필드만** 갱신한다. 값이 전부 같으면 아무 것도 손대지
  않는다(감사 컬럼도 그대로 유지) — SQLAlchemy 는 같은 값을 대입해도 dirty 로 잡으므로,
  대입 전에 값을 비교한다.
- 파일에 없고 DB에는 있다(활성 행) → 소프트 삭제한다(`deleted_by = system:seed-help`).
  콘텐츠 원본이 파일이므로, 파일에서 빠지면 그 키는 더 이상 쓰지 않는다는 뜻이다.

**검증(위반 시 시드 실패, 아무것도 커밋하지 않는다)**:
- 키 형식(`core/help_keys.validate_key`)
- 파일 안에서 (key, locale) 중복 없음
- `source` 가 있으면 `as_of` 도 있어야 한다(13.9-8 — 기준일 없는 규정 설명은 낡은 판단을 유도한다)
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.audit_context import SYSTEM_SEED_HELP, system_actor
from app.core.database import SessionLocal
from app.core.help_keys import validate_key
from app.models.help_text import HelpText

DATA_FILE = Path(__file__).resolve().parent / "data" / "help_texts_ko.json"

# 시드가 실제로 다루는 필드(비교·갱신 대상). id·감사 컬럼·row_version 은 여기 없다
_FIELDS = ("title", "body", "source", "as_of", "baseline_version", "sort_order")


@dataclass
class SeedReport:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    empty_body: list[str] = field(default_factory=list)


def load_entries(path: Path = DATA_FILE) -> list[dict]:
    """데이터 파일을 읽고 검증한다. 위반 시 ValueError(시드 실패, 아무것도 건드리지 않음)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    seen: set[tuple[str, str]] = set()
    entries = []
    for i, e in enumerate(raw):
        key = e["key"]
        locale = e.get("locale", "ko")
        validate_key(key)
        if (key, locale) in seen:
            raise ValueError(f"중복 키: {key!r} (locale={locale!r})")
        seen.add((key, locale))
        source = e.get("source")
        as_of_raw = e.get("as_of")
        if source and not as_of_raw:
            raise ValueError(f"'{key}' — source 가 있으면 as_of 도 있어야 합니다")
        entries.append({
            "key": key,
            "locale": locale,
            "title": e.get("title"),
            "body": e.get("body"),
            "source": source,
            "as_of": date.fromisoformat(as_of_raw) if as_of_raw else None,
            "baseline_version": e.get("baseline_version", 1),
            "sort_order": e.get("sort_order", i),
        })
    return entries


@system_actor(SYSTEM_SEED_HELP)
def seed(db: Session, entries: list[dict]) -> SeedReport:
    """entries 를 help_texts 에 멱등 upsert. 테스트도 이 함수를 직접 쓴다."""
    report = SeedReport()
    file_keys = {(e["key"], e["locale"]) for e in entries}

    existing = {
        (h.key, h.locale): h
        for h in db.query(HelpText).filter(HelpText.is_deleted == False).all()  # noqa: E712
    }

    for e in entries:
        k = (e["key"], e["locale"])
        row = existing.get(k)
        if row is None:
            row = HelpText(**e)
            db.add(row)
            report.created.append(e["key"])
        else:
            changed = False
            for f in _FIELDS:
                if getattr(row, f) != e[f]:
                    setattr(row, f, e[f])
                    changed = True
            if changed:
                report.updated.append(e["key"])
            else:
                report.unchanged.append(e["key"])
        if not e["body"]:
            report.empty_body.append(e["key"])

    for k, row in existing.items():
        if k not in file_keys:
            row.is_deleted = True
            report.deleted.append(row.key)

    db.flush()
    return report


def main() -> None:
    db = SessionLocal()
    try:
        entries = load_entries()
        report = seed(db, entries)
        db.commit()
        print(
            f"  생성 {len(report.created)} / 갱신 {len(report.updated)} / "
            f"변경없음 {len(report.unchanged)} / 삭제 {len(report.deleted)}"
        )
        if report.deleted:
            print(f"  삭제된 키: {report.deleted}")
        if report.empty_body:
            print(f"  문구 미작성({len(report.empty_body)}): {report.empty_body}")
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    argparse.ArgumentParser(description="매뉴얼 패널 문구 시드").parse_args()
    main()
