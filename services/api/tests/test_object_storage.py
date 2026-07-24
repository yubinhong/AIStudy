from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO

import pytest
from PIL import Image

from study_api.object_storage import ObjectStorageConfig, ObjectStorageError, S3ObjectStorage


def _valid_jpeg(byte_size: int = 1024) -> bytes:
    output = BytesIO()
    Image.new("RGB", (1, 1), color=(32, 128, 64)).save(output, format="JPEG")
    data = output.getvalue()
    assert len(data) < byte_size
    return data + b"\x00" * (byte_size - len(data))


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


class MultipartFakeS3Client(FakeS3Client):
    def __init__(self) -> None:
        super().__init__(body=b"", object_size=0)
        self.parts: dict[int, bytes] = {}
        self.aborted = False
        self.completed = False

    def head_bucket(self, Bucket: str) -> None:
        return None

    def create_multipart_upload(self, **kwargs: object) -> dict[str, str]:
        return {"UploadId": "synthetic-upload"}

    def upload_part(self, *, PartNumber: int, Body: bytes, **kwargs: object) -> dict[str, str]:
        self.parts[PartNumber] = Body
        return {"ETag": f"etag-{PartNumber}"}

    def complete_multipart_upload(
        self, *, MultipartUpload: dict[str, object], **kwargs: object
    ) -> None:
        self.body = b"".join(self.parts[number] for number in sorted(self.parts))
        self.object_size = len(self.body)
        self.completed = True

    def abort_multipart_upload(self, **kwargs: object) -> None:
        self.aborted = True

    def delete_object(self, **kwargs: object) -> None:
        self.body = b""
        self.object_size = 0


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
    client = FakeS3Client(body=_valid_jpeg())
    storage = S3ObjectStorage(
        ObjectStorageConfig("http://synthetic.local", "synthetic", "key", "secret"),
        client=client,  # type: ignore[arg-type]
    )

    expected_sha256 = sha256(client.body).hexdigest()
    storage.validate_uploaded_object(
        "captures/synthetic/source", "image/jpeg", 1024, expected_sha256
    )

    with pytest.raises(ObjectStorageError):
        storage.validate_uploaded_object(
            "captures/synthetic/source", "image/png", 1024, expected_sha256
        )

    with pytest.raises(ObjectStorageError, match="hash"):
        storage.validate_uploaded_object("captures/synthetic/source", "image/jpeg", 1024, "0" * 64)


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


def test_read_document_uses_the_private_curriculum_boundary() -> None:
    client = FakeS3Client(body=b"%PDF-local", object_size=10)
    storage = S3ObjectStorage(
        ObjectStorageConfig("http://synthetic.local", "synthetic", "key", "secret"),
        client=client,  # type: ignore[arg-type]
    )

    assert storage.read_document("curriculum/synthetic/source", max_bytes=1024) == b"%PDF-local"
    with pytest.raises(ObjectStorageError, match="curriculum prefix"):
        storage.read_document("captures/synthetic/source", max_bytes=1024)


@pytest.mark.asyncio
@pytest.mark.parametrize("byte_size", [1024, 5 * 1024 * 1024])
async def test_stream_capture_upload_uses_multipart_and_validates_the_completed_object(
    byte_size: int,
) -> None:
    client = MultipartFakeS3Client()
    data = _valid_jpeg(byte_size)
    storage = S3ObjectStorage(
        ObjectStorageConfig("http://synthetic.local", "synthetic", "key", "secret"),
        client=client,  # type: ignore[arg-type]
    )

    async def chunks():
        yield data[:100]
        yield data[100:]

    await storage.stream_capture_upload(
        "captures/synthetic/source",
        "image/jpeg",
        len(data),
        sha256(data).hexdigest(),
        chunks(),
    )

    assert client.completed is True
    assert client.aborted is False
    assert client.body == data


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


def test_presigned_upload_uses_public_client_but_private_reads_use_internal_client() -> None:
    internal_client = FakeS3Client()
    public_client = FakeS3Client()
    storage = S3ObjectStorage(
        ObjectStorageConfig(
            endpoint_url="http://minio:9000",
            bucket="synthetic",
            access_key_id="key",
            secret_access_key="secret",
            public_endpoint_url="http://192.0.2.10:9000",
        ),
        client=internal_client,  # type: ignore[arg-type]
        upload_client=public_client,  # type: ignore[arg-type]
    )

    storage.create_put_url("captures/synthetic", "image/jpeg", 1024)
    storage.read_object("captures/synthetic", max_bytes=1024)

    assert len(public_client.calls) == 1
    assert internal_client.calls == []


@pytest.mark.parametrize(
    "value",
    ["minio:9000", "ftp://192.0.2.10", "http://user:secret@192.0.2.10", "http://x/?q=1"],
)
def test_public_object_storage_endpoint_rejects_ambiguous_urls(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("OBJECT_STORAGE_ENDPOINT_URL", "http://minio:9000")
    monkeypatch.setenv("OBJECT_STORAGE_PUBLIC_ENDPOINT_URL", value)
    monkeypatch.setenv("CAPTURE_BUCKET", "synthetic")
    monkeypatch.setenv("MINIO_ROOT_USER", "key")
    monkeypatch.setenv("MINIO_ROOT_PASSWORD", "secret")

    with pytest.raises(ObjectStorageError, match="public object storage endpoint is invalid"):
        ObjectStorageConfig.from_environment()
