from pathlib import Path
from typing import Protocol


class AudioBlobStore(Protocol):
    """
    Where raw audio bytes live, independent of the record describing them.
    Kept as its own interface, separate from RecordStore (record_store.py),
    because per ADR 002 §1 blob storage and structured-record storage
    scale and migrate independently — swapping local disk for S3 later
    shouldn't require the database to change, and vice versa.
    """

    def save(self, asset_id: str, audio_format: str, data: bytes) -> Path: ...
    def delete(self, asset_id: str, audio_format: str) -> None: ...


class LocalTempBlobStore:
    """
    Only implementation this sprint: writes to a local temp directory.
    "Temporary" per this sprint's explicit scope — there is no cleanup
    job, retention policy, or cross-restart durability guarantee here.
    That's a deliberate, known gap (matching how ADR 002 leaves the real
    storage engine undecided), not an oversight.

    Files are named `{asset_id}.{format}` rather than the client's
    original filename — never trust a client-supplied filename for an
    on-disk path (path traversal / injection risk); the original filename
    is kept only as metadata on the AudioAsset record, for display.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, asset_id: str, audio_format: str) -> Path:
        return self._base_dir / f"{asset_id}.{audio_format}"

    def save(self, asset_id: str, audio_format: str, data: bytes) -> Path:
        path = self._path_for(asset_id, audio_format)
        path.write_bytes(data)
        return path

    def delete(self, asset_id: str, audio_format: str) -> None:
        self._path_for(asset_id, audio_format).unlink(missing_ok=True)
