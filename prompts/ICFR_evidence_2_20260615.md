# ICFR 작업5-2 — Evidence 다운로드 스트림(blob) 전환 명세

- **작성일**: 2026-06-15
- **대상**: `backend/app/api/evidence.py`, `backend/app/minio_client.py`
- **Tier**: Tier 2 (API 응답 계약 변경 → 마스터 push)
- **원칙**: ADR-0020 제로 추상화 (서비스 클래스·패턴 금지, 직접 함수만)

---

## 0. 배경 및 결정

현재 `GET /files/{file_id}/download`는 **presigned URL**(`{url, expires_in}`)을 반환한다. 그러나 프론트(Regina)는 **파일 스트림(blob)** 기준으로 구현했고, 보안·운영상 스트림 방식이 더 적합하다는 판단으로 백엔드를 **스트림 반환으로 전환**한다.

전환 이유:
- MinIO를 내부망에 은닉 가능 (외부에 endpoint·presigned URL 노출 불필요)
- 권한 검증이 백엔드 한 곳에 일관됨
- presigned의 internal/public endpoint 치환 문제 제거
- 프론트(스트림 구현)와 정렬되어 프론트 수정 불필요

**기존 코드 영향 검토**: 이 엔드포인트 소비처는 Regina 프론트(스트림 기대)뿐이라 정렬됨. 단 기존 download 테스트가 `url` 응답을 검증한다면 스트림 검증으로 수정 필요. `presigned_download_url`이 다른 곳에서 안 쓰이면 제거.

---

## 1. minio_client.py — get_object 함수 추가

MinIO에서 객체를 가져오는 함수 추가 (모듈 레벨 함수, 클래스 금지):

```python
def get_object_stream(object_key: str):
    """MinIO 객체 응답 반환. 호출측에서 stream 후 close/release_conn 책임."""
    return _client.get_object(settings.minio_bucket, object_key)
```

> `_client`는 기존 클라이언트 인스턴스명에 맞출 것. `get_object`는 urllib3 HTTPResponse를 반환하며, 사용 후 반드시 `close()` + `release_conn()` 호출해야 커넥션 누수가 없다 (아래 다운로드 핸들러에서 처리).

기존 `presigned_download_url`은 다른 사용처가 없으면 제거하고, `evidence.py`의 import에서도 뺀다.

---

## 2. evidence.py — download_file 스트림 전환

```python
from urllib.parse import quote
from fastapi.responses import StreamingResponse
from app.minio_client import get_object_stream, remove_object_safe, upload_object

@router.get("/files/{file_id}/download")
def download_file(file_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)):
    obj = db.query(EvidenceFile).filter(EvidenceFile.id == file_id, ...).first()
    if not obj:
        raise HTTPException(status_code=404, ...)
    if not obj.minio_key:
        raise HTTPException(status_code=409, detail="파일 본체 없음 (레거시 메타)")

    response = get_object_stream(obj.minio_key)

    def iterfile():
        try:
            for chunk in response.stream(32 * 1024):
                yield chunk
        finally:
            response.close()
            response.release_conn()

    # 한글 파일명 안전 처리 (RFC 5987)
    encoded = quote(obj.filename)
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"}
    return StreamingResponse(iterfile(), media_type=obj.mime_type, headers=headers)
```

핵심 주의:
- **반환 타입힌트 `-> dict` 제거** (StreamingResponse 반환)
- **한글 파일명** — `Content-Disposition`에 raw 한글 넣으면 헤더 인코딩 에러. 반드시 `filename*=UTF-8''<percent-encoded>` 형식 사용
- **커넥션 정리** — `finally`에서 `close()` + `release_conn()` 필수 (누수 방지)
- 권한·삭제 정합성 등 기존 로직은 유지

---

## 3. 테스트 수정

기존 download 테스트가 `{"url": ...}` 응답을 검증한다면:
- 응답 상태 200
- `Content-Type`이 업로드한 mime와 일치
- `Content-Disposition`에 filename 포함
- 응답 본문(bytes)이 업로드한 파일과 동일 (sha256 비교 권장)

업로드→다운로드 라운드트립으로 바이트 무결성 확인.

---

## 4. 완료 기준

- [ ] `minio_client.py`에 `get_object_stream` 추가, `presigned_download_url` 미사용 시 제거
- [ ] `download_file`이 `StreamingResponse`로 파일 스트림 반환
- [ ] 한글 파일명 정상 (RFC 5987 인코딩)
- [ ] 커넥션 close/release_conn 처리
- [ ] 업로드→다운로드 바이트 무결성 테스트 통과
- [ ] 이미지 재빌드 후 Swagger에서 다운로드 시 실제 파일 내려받기 확인

완료 후 `docker compose up -d --build backend` 재빌드하고, Swagger `GET /files/{id}/download`로 실제 파일이 다운로드되는지(브라우저가 파일로 받는지) 검증할 것.

---

ICFR_evidence_2_20260615.md 진행해줘
