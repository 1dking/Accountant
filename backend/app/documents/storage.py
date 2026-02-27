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
