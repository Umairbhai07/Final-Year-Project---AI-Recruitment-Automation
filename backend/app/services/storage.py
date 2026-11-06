"""File storage behind one interface: local disk for dev/tests, Supabase Storage (private bucket) for production."""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

import httpx

from app.config import settings

log = logging.getLogger(__name__)


class StorageError(Exception):
    pass


class StorageService(Protocol):
    def save(self, key: str, data: bytes, content_type: str) -> str: ...
    def load(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def delete_all(self) -> int: ...


class LocalStorage:
    """Stores files under LOCAL_STORAGE_DIR. Files are never served directly, only via authenticated endpoints."""

    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise StorageError("Invalid storage key")
        return path

    def save(self, key: str, data: bytes, content_type: str) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def load(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise StorageError(f"File not found: {key}")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def delete_all(self) -> int:
        """Removes every stored file (used by scripts/wipe.py). Returns how many files were removed."""
        files = [p for p in self.root.rglob("*") if p.is_file()]
        for p in files:
            p.unlink()
        for d in sorted((p for p in self.root.rglob("*") if p.is_dir()), reverse=True):
            d.rmdir()
        return len(files)


class SupabaseStorage:
    """Stores files in a PRIVATE Supabase Storage bucket using the service key (server-side only).

    Talks to the Storage REST API directly, so both key formats work: the new secret key (sb_secret_...) and the
    legacy service_role key (eyJ...).
    """

    def __init__(self, url: str, service_key: str, bucket: str):
        if not url or not service_key:
            raise StorageError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required for supabase storage")
        self.base = f"{url.rstrip('/')}/storage/v1/object"
        self.bucket = bucket
        self.client = httpx.Client(
            headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"}, timeout=60
        )

    def _url(self, key: str) -> str:
        return f"{self.base}/{self.bucket}/{quote(key)}"

    @staticmethod
    def _check(r: httpx.Response, action: str) -> None:
        if r.status_code >= 400:
            try:
                msg = r.json().get("message") or r.json().get("error") or r.text
            except ValueError:
                msg = r.text
            raise StorageError(f"{action} failed ({r.status_code}): {msg}")

    def save(self, key: str, data: bytes, content_type: str) -> str:
        try:
            r = self.client.post(
                self._url(key), content=data, headers={"content-type": content_type, "x-upsert": "true"}
            )
        except httpx.HTTPError as exc:
            raise StorageError(f"Upload failed: {exc}") from exc
        self._check(r, "Upload")
        return key

    def load(self, key: str) -> bytes:
        try:
            r = self.client.get(self._url(key))
        except httpx.HTTPError as exc:
            raise StorageError(f"Download failed: {exc}") from exc
        self._check(r, "Download")
        return r.content

    def delete(self, key: str) -> None:
        try:
            r = self.client.request("DELETE", f"{self.base}/{self.bucket}", json={"prefixes": [key]})
            self._check(r, "Delete")
        except (httpx.HTTPError, StorageError) as exc:
            log.warning("Could not delete %s: %s", key, exc)

    def _list(self, prefix: str) -> list[str]:
        """Every file key under `prefix`, walking into folders."""
        keys: list[str] = []
        offset = 0
        while True:
            r = self.client.post(
                f"{self.base}/list/{self.bucket}", json={"prefix": prefix, "limit": 1000, "offset": offset}
            )
            self._check(r, "List")
            items = r.json()
            for it in items:
                path = f"{prefix}/{it['name']}" if prefix else it["name"]
                if it.get("id") is None:  # a folder
                    keys += self._list(path)
                else:
                    keys.append(path)
            if len(items) < 1000:
                return keys
            offset += 1000

    def delete_all(self) -> int:
        """Removes every file in the bucket (used by scripts/wipe.py). Returns how many files were removed."""
        keys = self._list("")
        for i in range(0, len(keys), 100):
            r = self.client.request("DELETE", f"{self.base}/{self.bucket}", json={"prefixes": keys[i : i + 100]})
            self._check(r, "Delete")
        return len(keys)


@lru_cache
def get_storage() -> StorageService:
    if settings.STORAGE_BACKEND == "supabase":
        return SupabaseStorage(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY, settings.SUPABASE_BUCKET)
    return LocalStorage(settings.LOCAL_STORAGE_DIR)
