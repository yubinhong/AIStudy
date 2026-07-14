from hashlib import sha256
from urllib.request import Request, urlopen
from uuid import uuid4

import pytest

from study_api.object_storage import ObjectStorageConfig, S3ObjectStorage

pytestmark = pytest.mark.integration


def test_local_minio_accepts_a_bounded_synthetic_presigned_upload() -> None:
    storage = S3ObjectStorage(_local_minio_config())
    storage.ensure_bucket()
    content = b"\xff\xd8\xff\xe0synthetic-jpeg-only\xff\xd9"
    object_key = f"captures/{uuid4()}/{sha256(content).hexdigest()}.jpg"
    upload = storage.create_put_url(object_key, "image/jpeg", len(content))
    try:
        request = Request(
            upload.url,
            data=content,
            method="PUT",
            headers={"Content-Type": "image/jpeg"},
        )
        with urlopen(request, timeout=10) as response:  # noqa: S310 -- URL is server-generated.
            assert response.status in {200, 204}
        head = storage._client.head_object(Bucket=storage._config.bucket, Key=object_key)
        assert head["ContentLength"] == len(content)
        assert head["ContentType"] == "image/jpeg"
    finally:
        storage.delete_object(object_key)


def _local_minio_config() -> ObjectStorageConfig:
    return ObjectStorageConfig(
        endpoint_url="http://127.0.0.1:9000",
        bucket="study-captures-local",
        access_key_id="minio_local",
        secret_access_key="minio_local_only",
    )
