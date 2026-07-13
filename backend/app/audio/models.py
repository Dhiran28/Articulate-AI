from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

AudioFormat = Literal["wav", "mp3", "m4a", "webm"]

# Status is deliberately narrow this sprint — just "stored". ADR 002
# designs a fuller lifecycle (pending_transcription -> transcribing ->
# transcription_completed | transcription_failed), but nothing in this
# sprint ever reads or advances those values: there is no queue, no
# worker, and no transcription. Introducing them now would describe a
# process that doesn't exist yet and could never leave
# "pending_transcription" — a status a caller could reasonably wait on
# forever. The wider enum belongs to the sprint that actually builds the
# Transcription Service that fulfills it.
AudioAssetStatus = Literal["stored"]


class AudioAsset(BaseModel):
    """
    Canonical record of one uploaded audio file. Mirrors what ADR 002
    calls the Audio Service's output, trimmed to only what this sprint
    populates — no transcription-related fields exist here yet.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    original_filename: str
    format: AudioFormat
    content_type: str
    size_bytes: int
    status: AudioAssetStatus = "stored"
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
