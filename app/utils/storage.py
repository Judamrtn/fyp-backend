"""
File storage utility — supports local, MinIO, and AWS S3.
Configured via STORAGE_PROVIDER in .env:
  local  → saves to local filesystem (dev only)
  minio  → MinIO object storage
  s3     → AWS S3

Usage:
  from app.utils.storage import storage
  key  = storage.upload(file_bytes, filename, content_type)
  url  = storage.get_signed_url(key)
  storage.delete(key)
"""
import os
import uuid
from typing import Optional
from datetime import datetime
from app.config import settings


class LocalStorage:
    """Saves files to local filesystem. Dev only."""

    BASE_DIR = "/tmp/fyp_uploads"

    def upload(self, file_bytes: bytes, filename: str,
               content_type: str) -> str:
        os.makedirs(self.BASE_DIR, exist_ok=True)
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
        key = f"{uuid.uuid4()}.{ext}"
        path = os.path.join(self.BASE_DIR, key)
        with open(path, "wb") as f:
            f.write(file_bytes)
        return key

    def get_signed_url(self, key: str,
                       expires_in: int = None) -> str:
        return f"/api/v1/files/{key}"

    def delete(self, key: str) -> None:
        path = os.path.join(self.BASE_DIR, key)
        if os.path.exists(path):
            os.remove(path)

    def get_file(self, key: str) -> Optional[bytes]:
        path = os.path.join(self.BASE_DIR, key)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
        return None


class S3Storage:
    """AWS S3 or MinIO compatible storage."""

    def __init__(self):
        try:
            import boto3
            kwargs = {
                "aws_access_key_id":     settings.aws_access_key_id,
                "aws_secret_access_key": settings.aws_secret_access_key,
                "region_name":           settings.aws_region,
            }
            if settings.s3_endpoint_url:
                kwargs["endpoint_url"] = settings.s3_endpoint_url

            self.client = boto3.client("s3", **kwargs)
            self.bucket = settings.s3_bucket_name
        except Exception as e:
            raise RuntimeError(f"S3 storage init failed: {e}")

    def upload(self, file_bytes: bytes, filename: str,
               content_type: str) -> str:
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
        key = f"documents/{datetime.utcnow().strftime('%Y/%m')}/{uuid.uuid4()}.{ext}"
        self.client.put_object(
            Bucket      = self.bucket,
            Key         = key,
            Body        = file_bytes,
            ContentType = content_type,
        )
        return key

    def get_signed_url(self, key: str,
                       expires_in: int = None) -> str:
        expires = expires_in or settings.signed_url_expire_seconds
        return self.client.generate_presigned_url(
            "get_object",
            Params     = {"Bucket": self.bucket, "Key": key},
            ExpiresIn  = expires,
        )

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def get_file(self, key: str) -> Optional[bytes]:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except Exception:
            return None


def _get_storage():
    provider = settings.storage_provider.lower()
    if provider in ("s3", "minio"):
        return S3Storage()
    return LocalStorage()


# Singleton storage instance
storage = _get_storage()