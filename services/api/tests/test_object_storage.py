from datetime import UTC, datetime
from io import BytesIO

import pytest

from study_api.object_storage import ObjectStorageConfig, ObjectStorageError, S3ObjectStorage


class FakeS3Client:
    def __init__(self, body: bytes | None = None, object_size: int = 1024) -> None:
        self.calls: list[tuple[str, dict[str, object], int]] = []
        self.body = body if body is not None else b"x" * object_size
        self.object_size = object_size

    def generate_presigned_url(
        self, client_method: str, Params: dict[str, object], ExpiresIn: int
    ) -> str:
        self.calls.append((client_method, Params, ExpiresIn))
        return "http://synthetic.local/upload"

    def head_object(self, Bucket: str, Key: str) -> dict[str, object]:
        return {"ContentType": "image/jpeg; charset=binary", "ContentLength": self.object_size}

    def get_object(self, Bucket: str, Key: str) -> dict[str, object]:
        return {"Body": BytesIO(self.body)}


def test_presigned_upload_is_bounded_to_capture_media_and_ttl() -> None:
    client = FakeS3Client()
    storage = S3ObjectStorage(
        ObjectStorageConfig(
            endpoint_url="http://synthetic.local",
            bucket="synthetic-captures",
            access_key_id="synthetic",
            secret_access_key="synthetic",
            upload_ttl_seconds=300,
        ),
        client=client,  # type: ignore[arg-type]
    )

    upload = storage.create_put_url("captures/synthetic-id", "image/jpeg", 1024)

    assert upload.url == "http://synthetic.local/upload"
    assert upload.expires_at > datetime.now(UTC)
    assert client.calls == [
        (
            "put_object",
            {
                "Bucket": "synthetic-captures",
                "Key": "captures/synthetic-id",
                "ContentType": "image/jpeg",
                "ContentLength": 1024,
            },
            300,
        )
    ]


@pytest.mark.parametrize("object_key", ["other/synthetic-id", "captures/"])
def test_presigned_upload_rejects_unbounded_or_invalid_capture_keys(object_key: str) -> None:
    storage = S3ObjectStorage(
        ObjectStorageConfig("http://synthetic.local", "synthetic", "key", "secret"),
        client=FakeS3Client(),  # type: ignore[arg-type]
    )

    with pytest.raises(ObjectStorageError):
        storage.create_put_url(object_key, "image/jpeg", 1024)


def test_validate_uploaded_object_requires_matching_private_metadata() -> None:
    storage = S3ObjectStorage(
        ObjectStorageConfig("http://synthetic.local", "synthetic", "key", "secret"),
        client=FakeS3Client(),  # type: ignore[arg-type]
    )

    storage.validate_uploaded_object("captures/synthetic/source", "image/jpeg", 1024)

    with pytest.raises(ObjectStorageError):
        storage.validate_uploaded_object("captures/synthetic/source", "image/png", 1024)


def test_read_object_is_bounded_and_closes_the_response_body() -> None:
    client = FakeS3Client(body=b"x" * 1024)
    storage = S3ObjectStorage(
        ObjectStorageConfig("http://synthetic.local", "synthetic", "key", "secret"),
        client=client,  # type: ignore[arg-type]
    )

    assert storage.read_object("captures/synthetic/source", max_bytes=1024) == b"x" * 1024


def test_read_object_rejects_an_object_larger_than_the_requested_bound() -> None:
    storage = S3ObjectStorage(
        ObjectStorageConfig("http://synthetic.local", "synthetic", "key", "secret"),
        client=FakeS3Client(object_size=8_000_001),  # type: ignore[arg-type]
    )

    with pytest.raises(ObjectStorageError, match="bounded read limit"):
        storage.read_object("captures/synthetic/source", max_bytes=8_000_000)


def test_object_storage_configuration_requires_environment_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "OBJECT_STORAGE_ENDPOINT_URL",
        "CAPTURE_BUCKET",
        "MINIO_ROOT_USER",
        "MINIO_ROOT_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ObjectStorageError, match="configuration is incomplete"):
        ObjectStorageConfig.from_environment()
