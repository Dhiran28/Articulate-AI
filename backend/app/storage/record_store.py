from typing import Protocol

from app.audio.models import AudioAsset


class RecordStore(Protocol):
    """
    Where structured records (AudioAsset today; Transcript later, per
    ADR 002) live. Which real database backs this is an explicitly open
    decision (ADR 002 §1/§6) — InMemoryRecordStore below is a placeholder
    that satisfies this sprint's "store temporarily" requirement without
    committing to SQLite/Postgres/anything else before it's needed.
    """

    def create(self, asset: AudioAsset) -> None: ...
    def get(self, asset_id: str) -> AudioAsset | None: ...


class InMemoryRecordStore:
    """
    Only implementation this sprint: a plain dict, alive only for the
    lifetime of the running process. Explicitly not durable across
    restarts and not shared across multiple worker processes — acceptable
    because nothing in this sprint needs either property. Calling it out
    here means it's a known, chosen limitation, not a surprise discovered
    later.
    """

    def __init__(self) -> None:
        self._assets: dict[str, AudioAsset] = {}

    def create(self, asset: AudioAsset) -> None:
        self._assets[asset.id] = asset

    def get(self, asset_id: str) -> AudioAsset | None:
        return self._assets.get(asset_id)
