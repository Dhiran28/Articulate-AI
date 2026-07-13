from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol


@dataclass
class RawAudioUpload:
    """
    Audio as it exists the moment it arrives — just enough to identify it
    and read its bytes on demand. Deliberately doesn't know about
    AudioAsset, storage, or any particular web framework; that's what lets
    AudioService stay agnostic to which AudioIngestor produced this (see
    ADR 002 §1 — this is the AudioIngestor seam).
    """

    filename: str
    content_type: str | None
    read: Callable[[int], Awaitable[bytes]]
    """Reads up to `size` bytes; returns b"" at end of stream. Matches
    Starlette's UploadFile.read signature so HttpUploadIngestor can pass
    it straight through, but any future ingestor can supply its own."""


class AudioIngestor(Protocol):
    """
    Per ADR 002 §1: "a thing that accepts audio and hands the Audio
    Service validated bytes." HttpUploadIngestor (this sprint) is the
    only implementation; ESP32/Quest streaming ingestors are future work
    that will implement this same shape without AudioService changing.
    """

    async def ingest(self) -> RawAudioUpload: ...
