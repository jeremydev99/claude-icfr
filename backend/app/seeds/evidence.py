from app.seeds._shared import SeedContext


def seed(ctx: SeedContext) -> None:
    """EvidenceFile + EvidenceLink 시드 데이터."""

    from app.seeds.rcm import MAIN_CONTROL_KEY
    control_id = ctx.ids.get(MAIN_CONTROL_KEY)

    # EvidenceFile
    existing = ctx.get("/api/evidence/files")
    file_obj = next(
        (f for f in existing.get("items", []) if f["filename"] == "sales_review_2026Q1.pdf"),
        None,
    )
    if file_obj:
        print("  [evidence_files] sales_review_2026Q1.pdf exists (skip)")
    else:
        file_obj = ctx.post("/api/evidence/files", {
            "filename": "sales_review_2026Q1.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 204800,
            "minio_key": None,
        })
        print(f"  [evidence_files] sales_review_2026Q1.pdf created (id={file_obj['id']})")
    ctx.ids["evidence_file_001"] = file_obj["id"]

    if not control_id:
        print("  [evidence_links] MAIN_CONTROL 없음 — EvidenceLink 건너뜀")
        return

    # EvidenceLink: file → control
    existing_links = ctx.get("/api/evidence/links", params={"file_id": file_obj["id"]})
    linked = next(
        (lk for lk in existing_links.get("items", [])
         if lk["linked_entity_type"] == "control" and lk["linked_entity_id"] == control_id),
        None,
    )
    if linked:
        print(f"  [evidence_links] file→control exists (skip)")
    else:
        ctx.post("/api/evidence/links", {
            "file_id": file_obj["id"],
            "linked_entity_type": "control",
            "linked_entity_id": control_id,
        })
        print(f"  [evidence_links] file→control created")
