"""Storage backend abstraction for document file storage."""


import asyncio
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Protocol defining the storage backend interface."""

    async def save(self, data: bytes, extension: str) -> str:
        """Save file data and return the storage path."""
        ...

    async def read(self, storage_path: str) -> bytes:
        """Read and return file data from the given storage path."""
        ...

    async def delete(self, storage_path: str) -> None:
        """Delete the file at the given storage path."""
        ...

    async def exists(self, storage_path: str) -> bool:
        """Check whether a file exists at the given storage path."""
        ...


class LocalStorage:
    """Local filesystem storage backend.

    Stores files at {base_path}/{year}/{month}/{uuid}.{ext}
    """

    def __init__(self, base_path: str) -> None:
        self.base_path = Path(base_path)

    def _generate_path(self, extension: str) -> str:
        """Generate a date-partitioned storage path with a UUID filename."""
        now = datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        filename = f"{uuid.uuid4().hex}.{extension.lstrip('.')}"
        return f"{year}/{month}/{filename}"

    def _full_path(self, storage_path: str) -> Path:
        """Resolve a storage path to a full filesystem path."""
        return self.base_path / storage_path

    async def save(self, data: bytes, extension: str) -> str:
        """Save file data to a date-partitioned path and return the storage path."""
        storage_path = self._generate_path(extension)
        full_path = self._full_path(storage_path)

        # Create parent directories as needed
        await asyncio.to_thread(full_path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(full_path.write_bytes, data)

        return storage_path

    async def read(self, storage_path: str) -> bytes:
        """Read file data from the given storage path."""
        full_path = self._full_path(storage_path)
        if not await asyncio.to_thread(full_path.exists):
            raise FileNotFoundError(f"File not found at storage path: {storage_path}")
        return await asyncio.to_thread(full_path.read_bytes)

    async def delete(self, storage_path: str) -> None:
        """Delete the file at the given storage path."""
        full_path = self._full_path(storage_path)
        if await asyncio.to_thread(full_path.exists):
            await asyncio.to_thread(full_path.unlink)

    async def exists(self, storage_path: str) -> bool:
        """Check whether a file exists at the given storage path."""
        full_path = self._full_path(storage_path)
        return await asyncio.to_thread(full_path.exists)

    def get_full_path(self, storage_path: str) -> Path:
        """Return the full filesystem path for a storage path."""
        return self._full_path(storage_path)


class R2Storage:
    """Cloudflare R2 storage backend (S3-compatible)."""

    def __init__(
        self,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
    ) -> None:
        import boto3

        self.bucket_name = bucket_name
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

    def _generate_key(self, extension: str) -> str:
        now = datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        filename = f"{uuid.uuid4().hex}.{extension.lstrip('.')}"
        return f"{year}/{month}/{filename}"

    async def save(self, data: bytes, extension: str) -> str:
        key = self._generate_key(extension)
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self.bucket_name,
            Key=key,
            Body=data,
        )
        return key

    async def read(self, storage_path: str) -> bytes:
        try:
            resp = await asyncio.to_thread(
                self._client.get_object,
                Bucket=self.bucket_name,
                Key=storage_path,
            )
            return await asyncio.to_thread(resp["Body"].read)
        except Exception as exc:
            raise FileNotFoundError(
                f"File not found in R2 at key: {storage_path}"
            ) from exc

    async def delete(self, storage_path: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object,
            Bucket=self.bucket_name,
            Key=storage_path,
        )

    async def exists(self, storage_path: str) -> bool:
        try:
            await asyncio.to_thread(
                self._client.head_object,
                Bucket=self.bucket_name,
                Key=storage_path,
            )
            return True
        except Exception:
            return False


def build_storage(settings) -> StorageBackend:
    """Build the appropriate storage backend based on settings."""
    if settings.storage_type == "r2" and settings.r2_access_key_id:
        return R2Storage(
            endpoint_url=settings.r2_endpoint,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            bucket_name=settings.r2_bucket_name,
        )
    return LocalStorage(settings.storage_path)
