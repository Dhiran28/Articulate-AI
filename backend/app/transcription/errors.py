from enum import Enum


class TranscriptionErrorReason(str, Enum):
    """
    Machine-readable cause of a failed transcription attempt — same
    "reason, not just message" principle as AudioValidationReason
    (app/audio/errors.py), so the API layer can map each one to the right
    HTTP status.
    """

    ASSET_NOT_FOUND = "asset_not_found"
    PROVIDER_MISCONFIGURED = "provider_misconfigured"
    PROVIDER_ERROR = "provider_error"


class TranscriptionError(Exception):
    """Raised when transcription can't proceed or fails partway through."""

    def __init__(self, reason: TranscriptionErrorReason, message: str) -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)
