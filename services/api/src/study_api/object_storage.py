"""Private S3-compatible storage adapter for Capture media.

The adapter only exposes bounded private-object operations. It never logs credentials,
object keys, or presigned URLs, and it does not make buckets public.
"""

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Protocol

import boto3  # type: ignore[import-untyped]
from botocore.client import BaseClient  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]


class ObjectStorageError(Exception):
    """Raised when local object storage cannot satisfy a bounded operation."""


class UploadUrlClient(Protocol):
    def generate_presigned_url(
        self, client_method: str, Params: dict[str, object], ExpiresIn: int
    ) -> str: ...


class CaptureObjectStorage(Protocol):
    def ensure_bucket(self) -> None: ...

    def create_put_url(
        self, object_key: str, content_type: str, byte_size: int
    ) -> "PresignedUpload": ...

    def validate_uploaded_object(
        self, object_key: str, content_type: str, byte_size: int, content_sha256: str
    ) -> None: ...

    def read_object(self, object_key: str, max_bytes: int) -> bytes: ...

    def delete_object(self, object_key: str) -> None: ...


class UnavailableObjectStorage:
    """Safe fallback when object-storage configuration was not supplied."""

    def ensure_bucket(self) -> None:
        raise ObjectStorageError("object storage is not configured")

    def create_put_url(
        self, object_key: str, content_type: str, byte_size: int
    ) -> "PresignedUpload":
        raise ObjectStorageError("object storage is not configured")

    def validate_uploaded_object(
        self, object_key: str, content_type: str, byte_size: int, content_sha256: str
    ) -> None:
        raise ObjectStorageError("object storage is not configured")

    def read_object(self, object_key: str, max_bytes: int) -> bytes:
        raise ObjectStorageError("object storage is not configured")

    def delete_object(self, object_key: str) -> None:
        raise ObjectStorageError("object storage is not configured")


@dataclass(frozen=True)
class ObjectStorageConfig:
    endpoint_url: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    upload_ttl_seconds: int = 300
    region_name: str = "us-east-1"

    @classmethod
    def from_environment(cls) -> "ObjectStorageConfig":
        try:
            ttl = int(os.environ.get("CAPTURE_UPLOAD_TTL_SECONDS", "300"))
        except ValueError as error:
            raise ObjectStorageError("capture upload TTL must be an integer") from error
        if not 1 <= ttl <= 900:
            raise ObjectStorageError("capture upload TTL must be between 1 and 900 seconds")
        required = {
            "OBJECT_STORAGE_ENDPOINT_URL": os.environ.get("OBJECT_STORAGE_ENDPOINT_URL"),
            "CAPTURE_BUCKET": os.environ.get("CAPTURE_BUCKET"),
            "MINIO_ROOT_USER": os.environ.get("MINIO_ROOT_USER"),
            "MINIO_ROOT_PASSWORD": os.environ.get("MINIO_ROOT_PASSWORD"),
        }
        if any(value is None or not value.strip() for value in required.values()):
            raise ObjectStorageError("object storage configuration is incomplete")
        return cls(
            endpoint_url=required["OBJECT_STORAGE_ENDPOINT_URL"] or "",
            bucket=required["CAPTURE_BUCKET"] or "",
            access_key_id=required["MINIO_ROOT_USER"] or "",
            secret_access_key=required["MINIO_ROOT_PASSWORD"] or "",
            upload_ttl_seconds=ttl,
        )


@dataclass(frozen=True)
class PresignedUpload:
    url: str
    expires_at: datetime


class S3ObjectStorage:
    """Minimal private-bucket interface used by the Capture application layer."""

    def __init__(self, config: ObjectStorageConfig, client: BaseClient | None = None) -> None:
        self._config = config
        self._client = client or boto3.client(
            "s3",
            endpoint_url=config.endpoint_url,
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            region_name=config.region_name,
        )

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._config.bucket)
        except ClientError as error:
            code = str(error.response.get("Error", {}).get("Code", ""))
            if code not in {"404", "NoSuchBucket"}:
                raise ObjectStorageError("object storage bucket is unavailable") from error
            try:
                self._client.create_bucket(Bucket=self._config.bucket)
            except ClientError as create_error:
                raise ObjectStorageError(
                    "object storage bucket could not be created"
                ) from create_error

    def create_put_url(self, object_key: str, content_type: str, byte_size: int) -> PresignedUpload:
        if not object_key.startswith("captures/") or object_key == "captures/":
            raise ObjectStorageError("capture object key must use the captures prefix")
        if content_type not in {"image/jpeg", "image/png"}:
            raise ObjectStorageError("capture media type is not allowed")
        if not 1 <= byte_size <= 8_000_000:
            raise ObjectStorageError("capture byte size is not allowed")
        expires_at = datetime.now(UTC) + timedelta(seconds=self._config.upload_ttl_seconds)
        url = self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._config.bucket,
                "Key": object_key,
                "ContentType": content_type,
                "ContentLength": byte_size,
            },
            ExpiresIn=self._config.upload_ttl_seconds,
        )
        return PresignedUpload(url=url, expires_at=expires_at)

    def validate_uploaded_object(
        self, object_key: str, content_type: str, byte_size: int, content_sha256: str
    ) -> None:
        """Confirm private object metadata before advancing Capture state."""

        try:
            response = self._client.head_object(Bucket=self._config.bucket, Key=object_key)
        except ClientError as error:
            raise ObjectStorageError("uploaded capture object is unavailable") from error
        actual_type = str(response.get("ContentType", "")).split(";", maxsplit=1)[0]
        actual_size = response.get("ContentLength")
        if actual_type != content_type or actual_size != byte_size:
            raise ObjectStorageError("uploaded capture object metadata does not match declaration")
        actual_sha256 = sha256(self.read_object(object_key, max_bytes=byte_size)).hexdigest()
        if actual_sha256 != content_sha256:
            raise ObjectStorageError("uploaded capture object hash does not match declaration")

    def read_object(self, object_key: str, max_bytes: int) -> bytes:
        """Read one bounded private object into memory for the OCR boundary."""

        if not object_key.startswith("captures/") or object_key == "captures/":
            raise ObjectStorageError("capture object key must use the captures prefix")
        if not 1 <= max_bytes <= 8_000_000:
            raise ObjectStorageError("capture read limit is not allowed")
        body: object | None = None
        try:
            metadata = self._client.head_object(Bucket=self._config.bucket, Key=object_key)
            actual_size = metadata.get("ContentLength")
            if not isinstance(actual_size, int) or not 1 <= actual_size <= max_bytes:
                raise ObjectStorageError("capture object exceeds the bounded read limit")
            response = self._client.get_object(Bucket=self._config.bucket, Key=object_key)
            body = response.get("Body")
            if body is None:
                raise ObjectStorageError("capture object body is unavailable")
            data = body.read(max_bytes + 1)  # type: ignore[union-attr]
            if not isinstance(data, bytes) or len(data) > max_bytes:
                raise ObjectStorageError("capture object exceeds the bounded read limit")
            return data
        except ObjectStorageError:
            raise
        except (ClientError, OSError, TypeError, ValueError) as error:
            raise ObjectStorageError("capture object could not be read") from error
        finally:
            if body is not None:
                close = getattr(body, "close", None)
                if callable(close):
                    close()

    def delete_object(self, object_key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._config.bucket, Key=object_key)
        except ClientError as error:
            raise ObjectStorageError("capture object could not be deleted") from error
