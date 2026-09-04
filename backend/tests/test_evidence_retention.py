"""증빙 삭제 시 파일·이력 보존 검증 (3-3, ADR-0032 §2.4).

**핵심은 `test_deleted_evidence_file_survives_in_storage` 다.**
파일이 남는지를 보지 않으면 파일을 지우는 구현도 "삭제 후 조회에서 제외" 만으로
통과한다 — 수정 전 코드가 정확히 그 상태였다(운영에서 `is_deleted=true` 인 2건의
MinIO 객체가 이미 사라져 있었다).

MinIO 는 테스트 환경에 없으므로 `app.api.evidence` 의 저장소 호출을 대역으로 바꿔
**"삭제 경로가 저장소 삭제를 호출하지 않는다"** 를 직접 고정한다. 실제 객체 잔존은
운영에서 `mc ls` 로 확인한다(§5-6).
"""
import io

import pytest
from fastapi.testclient import TestClient

from app.api import evidence as evidence_api


@pytest.fixture
def fake_storage(monkeypatch):
    """업로드/다운로드를 메모리 대역으로 바꾼다. 삭제 호출은 **일부러 뚫어두지 않는다** —
    수정 후 코드에는 저장소 삭제 경로 자체가 없어야 하기 때문이다."""
    store: dict[str, bytes] = {}

    def _upload(object_key: str, data_bytes: bytes, content_type: str) -> None:
        store[object_key] = data_bytes

    class _Resp:
        def __init__(self, data: bytes):
            self._buf = io.BytesIO(data)

        def stream(self, chunk_size: int = 8192):
            while True:
                chunk = self._buf.read(chunk_size)
                if not chunk:
                    return
                yield chunk

        def close(self):
            pass

        def release_conn(self):
            pass

    def _get(object_key: str):
        return _Resp(store[object_key])

    monkeypatch.setattr(evidence_api, "upload_object", _upload)
    monkeypatch.setattr(evidence_api, "get_object_stream", _get)
    return store


def _headers(client: TestClient) -> dict:
    resp = client.post("/api/auth/login",
                       data={"username": "admin@acme.example", "password": "admin123"})
    assert resp.status_code == 200
    return {"Authorization": "Bearer " + resp.json()["access_token"]}


def _upload(client: TestClient, h: dict, name: str, body: bytes = b"%PDF-1.4 test"):
    return client.post("/api/evidence/files", headers=h,
                       files={"file": (name, body, "application/pdf")})


def test_evidence_module_has_no_storage_delete_path(client: TestClient) -> None:
    """**저장소 삭제 함수가 증빙 모듈에 import 되어 있지 않다** (ADR-0032 §2.4).

    수정 전에는 `remove_object_safe` 를 import 해 삭제 시 호출했다. 호출을 지우고
    import 를 남겨두면 다음 사람이 "있으니 쓰라는 뜻"으로 읽는다 — 경로 자체를 없앤다.
    """
    assert not hasattr(evidence_api, "remove_object_safe")


def test_deleted_evidence_file_survives_in_storage(client: TestClient, fake_storage) -> None:
    """§5-6 **핵심** — 삭제해도 저장소 객체가 남는다.

    레코드만 남기고 파일을 지우면 "그때 지운 게 뭐였나"에 답할 수 없다.
    보존기간이 5년 이상이므로 파일도 그 기간을 따른다(§2.9).
    """
    h = _headers(client)
    created = _upload(client, h, "보존검증.pdf")
    assert created.status_code == 201, created.text
    fid = created.json()["id"]
    key = created.json()["minio_key"]
    assert key in fake_storage

    assert client.delete(f"/api/evidence/files/{fid}", headers=h).status_code == 204
    assert key in fake_storage          # 파일이 남아 있다


def test_deleted_evidence_is_excluded_from_list(client: TestClient, fake_storage) -> None:
    """§5-5(전반) — 삭제 후 목록·상세 조회에서 제외된다."""
    h = _headers(client)
    fid = _upload(client, h, "목록제외.pdf").json()["id"]
    ids = {f["id"] for f in client.get("/api/evidence/files",
                                       params={"limit": 500}, headers=h).json()["items"]}
    assert fid in ids

    client.delete(f"/api/evidence/files/{fid}", headers=h)
    ids = {f["id"] for f in client.get("/api/evidence/files",
                                       params={"limit": 500}, headers=h).json()["items"]}
    assert fid not in ids
    assert client.get(f"/api/evidence/files/{fid}", headers=h).status_code == 404


def test_delete_history_records_who_and_when(client: TestClient, fake_storage) -> None:
    """§5-5(후반) — 이력 조회에 업로더·업로드시각·삭제자·삭제시각·사유가 나온다.

    "누가 언제 올렸다가 지웠는지"가 감사에서 실제로 묻는 질문이다.
    """
    h = _headers(client)
    fid = _upload(client, h, "이력검증.pdf").json()["id"]

    before = client.get(f"/api/evidence/files/{fid}/history", headers=h).json()
    assert before["is_deleted"] is False
    assert before["uploaded_by_name"] == "System Administrator"
    assert before["uploaded_at"]
    assert before["deleted_at"] is None

    client.delete(f"/api/evidence/files/{fid}", headers=h, params={"reason": "오등록 정정"})

    after = client.get(f"/api/evidence/files/{fid}/history", headers=h).json()
    assert after["is_deleted"] is True
    assert after["uploaded_by_name"] == "System Administrator"
    assert after["deleted_by_name"] == "System Administrator"
    assert after["deleted_at"]
    assert after["delete_reason"] == "오등록 정정"
    # 삭제 후에도 저장소 키가 남아 파일 소재를 알 수 있다
    assert after["minio_key"]


def test_history_endpoint_reads_deleted_records(client: TestClient, fake_storage) -> None:
    """이력 엔드포인트는 `is_deleted` 를 필터하지 않는다 — 삭제된 것을 보는 것이 목적이다."""
    h = _headers(client)
    fid = _upload(client, h, "삭제조회.pdf").json()["id"]
    client.delete(f"/api/evidence/files/{fid}", headers=h)

    resp = client.get(f"/api/evidence/files/{fid}/history", headers=h)
    assert resp.status_code == 200          # 상세(404)와 달리 조회된다
    assert resp.json()["is_deleted"] is True


def test_korean_filename_roundtrip(client: TestClient, fake_storage) -> None:
    """§5-3 — 한글 파일명 업로드·다운로드. 원본명이 그대로 돌아온다."""
    h = _headers(client)
    created = _upload(client, h, "2026년 1분기 대사표.pdf")
    assert created.status_code == 201, created.text
    assert created.json()["filename"] == "2026년 1분기 대사표.pdf"

    resp = client.get(f"/api/evidence/files/{created.json()['id']}/download", headers=h)
    assert resp.status_code == 200
    assert "2026" in resp.headers.get("content-disposition", "")


def test_same_filename_uploaded_twice_both_kept(client: TestClient, fake_storage) -> None:
    """§5-4 — 같은 이름 파일을 두 번 올려도 둘 다 보존된다(저장 키가 다르다)."""
    h = _headers(client)
    a = _upload(client, h, "중복이름.pdf", b"%PDF-1.4 first").json()
    b = _upload(client, h, "중복이름.pdf", b"%PDF-1.4 second longer").json()
    assert a["id"] != b["id"]
    assert a["minio_key"] != b["minio_key"]
    assert a["minio_key"] in fake_storage and b["minio_key"] in fake_storage
