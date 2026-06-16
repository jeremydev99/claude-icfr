# ICFR 작업5 — Evidence MinIO 연동 구현 명세

- **작성일**: 2026-06-15
- **대상**: `backend/app/api/evidence.py`, `models/evidence.py`, MinIO 연동
- **Tier**: Tier 2 (모델·스키마 변경 + 신규 기능 → 마스터 push)
- **원칙**: ADR-0020 제로 추상화 (서비스 클래스·디자인 패턴 금지, 직접 함수·명시적 if만)

---

## 0. 배경

Evidence 모듈은 현재 메타데이터·링크 CRUD 껍데기만 있고, 실제 파일 저장/다운로드가 비어 있다. `create_file`은 `EvidenceFileCreate` body(메타데이터)만 받아 DB에 저장하며 `minio_key`는 NULL로 남는다. 본 작업은 MinIO 실연동을 채워 증빙 파일이 실제로 저장·다운로드되게 한다.

MinIO 설정은 `config.py`에 이미 존재한다 (`minio_endpoint`, `minio_root_user`, `minio_root_password`, `minio_bucket=icfr-evidence`, `minio_use_ssl`, `minio_public_endpoint`). 그대로 활용한다.

**기존 코드 영향 검토 (필수)**: 작업 시작 전 `EvidenceFileCreate` 스키마와 기존 `POST /files`(메타 전용) 호출처를 grep으로 확인할 것. 프론트엔드(Regina)에 Evidence 화면이 아직 없으면 업로드 엔드포인트를 multipart로 전면 전환해도 무방하다. 사용처가 있으면 보고 후 결정.

---

## 1. 의존성

`minio` 파이썬 패키지 설치 (requirements 또는 pyproject에 추가):

```
minio
```

설치 후 Docker 이미지 재빌드 필요 (`docker compose up -d --build backend`). **빌드 누락 시 변경 미반영** — 5/22 구버전 이미지 함정 반복 주의.

---

## 2. 모델 변경 — sha256 무결성 컬럼 추가

`backend/app/models/evidence.py`의 `EvidenceFile`에 컬럼 추가:

```python
sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

기존 행 호환 위해 nullable. 신규 업로드는 항상 채운다.

### alembic 마이그레이션

```
docker compose exec backend alembic revision --autogenerate -m "evidence sha256 column"
docker compose exec backend alembic upgrade head
```

autogenerate 결과에 `add_column('evidence_files', 'sha256', ...)`만 포함되는지 확인 후 적용 (의도치 않은 drop 없는지 검토).

---

## 3. MinIO 클라이언트 모듈

`backend/app/minio_client.py` 신규 생성. **클래스 래퍼 금지, 모듈 레벨 함수로** (ADR-0020).

요구사항:
- `config.py` 설정으로 `Minio` 클라이언트 단일 인스턴스 생성
- `ensure_bucket()` 함수 — 버킷 없으면 생성 (`bucket_exists` → `make_bucket`)
- 앱 시작 시 `ensure_bucket()` 호출 (`main.py`의 startup. 기존 startup 패턴 따를 것)
- `upload_object(object_key, data_bytes, content_type)` — `put_object`
- `presigned_download_url(object_key, expires_seconds)` — `presigned_get_object`
- `remove_object_safe(object_key)` — `remove_object`, 객체 없어도 예외 무시

---

## 4. 업로드 — POST /files (multipart 전환)

기존 메타 전용 `create_file`을 multipart 파일 업로드로 전환:

```python
from fastapi import UploadFile, File

@router.post("/files", status_code=status.HTTP_201_CREATED, response_model=EvidenceFileRead)
async def create_file(file: UploadFile = File(...), user: CurrentUser = None, db: Session = Depends(get_db)) -> EvidenceFile:
```

처리 순서 (명시적, 추상화 없이):
1. `data = await file.read()`
2. 크기 검증 — `len(data)`가 `settings.max_upload_bytes` 초과 시 413 반환
3. mime 검증 — `file.content_type`이 허용 목록에 없으면 415 반환
4. `sha256 = hashlib.sha256(data).hexdigest()`
5. `minio_key = f"{uuid4()}/{file.filename}"` (충돌 방지 prefix)
6. `upload_object(minio_key, data, file.content_type)`
7. `EvidenceFile(filename=..., mime_type=..., size_bytes=len(data), minio_key=minio_key, sha256=sha256, uploaded_by_id=user.id)` 저장
8. MinIO 업로드 성공 후에만 DB commit (업로드 실패 시 DB 미기록)

`config.py`에 추가:
```python
max_upload_bytes: int = 52428800  # 50MB
```

허용 mime 목록 (상수, evidence.py 상단):
```python
ALLOWED_MIME = {
    "application/pdf",
    "image/png", "image/jpeg",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "application/haansofthwp",  # hwp
    "application/x-hwp",
}
```

---

## 5. 다운로드 — GET /files/{file_id}/download

```python
@router.get("/files/{file_id}/download")
def download_file(file_id: UUID, user: CurrentUser = None, db: Session = Depends(get_db)) -> dict:
```

- 파일 조회, 없으면 404
- `minio_key`가 NULL이면 409 (레거시 메타 전용 행)
- `presigned_download_url(minio_key, 900)` (15분) 발급
- `{"url": presigned_url, "expires_in": 900}` 반환

presigned URL은 `minio_public_endpoint` 기준으로 발급되어 브라우저가 직접 다운로드 가능해야 함. 내부 endpoint(`minio:9000`)와 공개 endpoint 불일치 시 URL 호스트 치환 필요 — 동작 확인 시 반드시 브라우저에서 실제 다운로드되는지 검증.

---

## 6. 삭제 정합성 — DELETE /files/{file_id}

기존 `delete_file`은 DB만 삭제. MinIO object 동반 제거 추가:
1. 파일 조회
2. `minio_key` 있으면 `remove_object_safe(minio_key)`
3. DB 삭제

---

## 7. 테스트

`backend/tests/test_modules.py` 또는 신규 `test_evidence.py`:
- 업로드 → 201, sha256·minio_key 채워짐 확인
- 크기 초과 → 413
- 비허용 mime → 415
- 다운로드 → presigned URL 반환
- 삭제 → DB·MinIO 모두 제거

MinIO 컨테이너가 떠 있어야 통과 (`docker compose ps`로 minio 확인).

---

## 8. 완료 기준

- [ ] `minio` 패키지 설치 + 이미지 재빌드
- [ ] sha256 컬럼 추가 + 마이그레이션 적용
- [ ] 버킷 자동 생성 (앱 시작 시)
- [ ] 파일 업로드 → MinIO 저장 + 메타·sha256 DB 기록
- [ ] presigned 다운로드 URL 발급 + 브라우저 실다운로드 확인
- [ ] 삭제 시 DB·MinIO 정합성
- [ ] 크기·mime 검증 동작
- [ ] 테스트 통과

완료 후 `docker compose up -d --build backend`로 재빌드하고 실제 업로드→다운로드→삭제 1회 수행해 검증할 것.

---

ICFR_evidence_1_20260615.md 진행해줘
