"""MinIO 저장소 접근 — ADR-0032 §2.2·§2.3.

**테넌트 격리가 경로 분리다.** 버킷을 테넌트별로 나누지 않는다 — 온보딩마다 버킷
생성이 필요하고 고객사 서버 설치 시 MinIO 설정 절차가 늘어난다.

**경로 분리는 DB 의 복합 FK 같은 구조적 보장이 없다.** 애플리케이션이 경로를 잘못
만들면 다른 테넌트 파일에 닿는다. 그래서 **경로를 만드는 곳은
`build_evidence_key` 하나뿐**이고, 다른 곳에서 문자열을 이어붙이지 않는다.

`tenant_id` 는 그 함수가 컨텍스트에서 **직접** 가져온다 — 호출자가 넘기면 잘못된
값을 넘길 수 있다.
"""
import io

from minio import Minio
from minio.error import S3Error

from app.config import get_settings
from app.core.tenant_context import get_active_tenant

settings = get_settings()

_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_root_user,
    secret_key=settings.minio_root_password,
    secure=settings.minio_use_ssl,
)


def ensure_bucket() -> None:
    if not _client.bucket_exists(settings.minio_bucket):
        _client.make_bucket(settings.minio_bucket)


def upload_object(object_key: str, data_bytes: bytes, content_type: str) -> None:
    _client.put_object(
        settings.minio_bucket,
        object_key,
        io.BytesIO(data_bytes),
        length=len(data_bytes),
        content_type=content_type,
    )


def get_object_stream(object_key: str):
    """MinIO 객체 응답 반환. 호출측에서 stream 후 close/release_conn 책임."""
    return _client.get_object(settings.minio_bucket, object_key)


def remove_object_safe(object_key: str) -> None:
    try:
        _client.remove_object(settings.minio_bucket, object_key)
    except S3Error:
        pass


def build_evidence_key(cycle_id, control_id, evidence_id) -> str:
    """증빙 저장 경로. **이 함수만 경로를 만든다** (ADR-0032 §2.2).

        {tenant_id}/cycles/{cycle_id}/controls/{control_id}/{evidence_id}

    `tenant_id` 를 인자로 받지 않는다 — 활성 tenant 를 컨텍스트에서 직접 읽는다.
    호출자가 넘기면 잘못된 값을 넘길 수 있고, 그러면 다른 테넌트 경로에 쓰게 된다.

    **파일명을 경로에 쓰지 않는다** (§2.3). 내부 식별자(`evidence_id`)로 저장하고
    원본 파일명은 DB 에 둔다 — 한글 파일명·중복 이름·경로 조작 시도가 한 번에
    해결된다. 다운로드 시 `Content-Disposition` 으로 원본명을 내려주므로 사용자는
    차이를 느끼지 않는다.

    **다운로드에서 이 함수를 다시 부르지 않는다.** DB 레코드의 `minio_key` 를 쓴다 —
    경로를 계산해 읽으면 기존 레거시 경로(tenant 없음)를 못 읽고, 무엇보다 경로가
    판정 근거가 되어 버린다(§2.2 — 경로로 판정하지 않는다).
    """
    tenant_id = get_active_tenant()
    if tenant_id is None:
        raise RuntimeError(
            "활성 tenant 가 없습니다 — 증빙 경로를 만들 수 없습니다. "
            "테넌트 컨텍스트 없이 증빙을 저장하면 격리가 깨진다."
        )
    return f"{tenant_id}/cycles/{cycle_id}/controls/{control_id}/{evidence_id}"
