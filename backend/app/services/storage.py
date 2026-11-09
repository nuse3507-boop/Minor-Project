"""Private encrypted originals. A deployment must supply and back up STORAGE_KEY."""

import hashlib
import os
import uuid
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class StorageError(RuntimeError):
    """Safe storage failure that never includes a key or document body."""


def _publish_once(target: Path, data: bytes):
    """Publish a complete small metadata file without a cross-process empty-file window."""
    temporary = target.parent / (".storage-" + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            pass
    finally:
        temporary.unlink(missing_ok=True)


def cipher():
    cfg = settings()
    root = cfg.storage_path.resolve()
    root.mkdir(parents=True, exist_ok=True)
    key = cfg.storage_key.encode()
    if not key:
        key_path = root / ".storage-key"
        if not key_path.exists():
            if any(root.rglob("*.enc")):
                raise StorageError(
                    "The original private storage key is missing. Restore it before accessing retained documents."
                )
            _publish_once(key_path, Fernet.generate_key())
        key = key_path.read_bytes()
    try:
        value = Fernet(key)
    except (ValueError, TypeError) as exc:
        raise StorageError(
            "Private storage encryption key is invalid. Restore the configured original key."
        ) from exc
    return value


def path(key: str) -> Path:
    root = settings().storage_path.resolve()
    target = (root / key).resolve()
    valid_parent = target.parent == root or (
        target.parent.parent == root
        and target.parent.name.startswith("key-")
        and len(target.parent.name) == 20
    )
    if not valid_parent or not key.endswith(".enc") or ".." in key or "\\" in key:
        raise ValueError("Invalid private object identifier")
    return target


def write(data: bytes, source_id: str):
    value = cipher()
    key_bytes = (
        settings().storage_key.encode() or (settings().storage_path.resolve() / ".storage-key").read_bytes()
    )
    fingerprint = hashlib.sha256(key_bytes).hexdigest()[:16]
    key = f"key-{fingerprint}/{source_id}.enc"
    path(key).parent.mkdir(parents=True, exist_ok=True)
    encrypted = value.encrypt(data)
    with path(key).open("xb") as file:
        file.write(encrypted)
        file.flush()
        os.fsync(file.fileno())
    return key, hashlib.sha256(data).hexdigest()


def read(key: str, expected_hash: str):
    encrypted = path(key).read_bytes()
    try:
        data = cipher().decrypt(encrypted)
    except InvalidToken:
        # Legacy flat originals can use their preserved development key. Never rewrite it.
        legacy = settings().storage_path.resolve() / ".storage-key"
        if "/" in key or not legacy.exists():
            raise StorageError("The configured storage key cannot decrypt this retained source.") from None
        try:
            data = Fernet(legacy.read_bytes()).decrypt(encrypted)
        except (InvalidToken, ValueError):
            raise StorageError("Restore the original encryption key to read this retained source.") from None
    if hashlib.sha256(data).hexdigest() != expected_hash:
        raise ValueError("Source integrity validation failed")
    return data


def remove(key: str):
    path(key).unlink(missing_ok=True)
