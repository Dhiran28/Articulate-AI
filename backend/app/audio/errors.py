from enum import Enum


class AudioValidationReason(str, Enum):
    """
    Machine-readable cause of an upload rejection. Kept distinct from the
    human-readable message so the API layer can map each reason to the
    right HTTP status code, and so a future frontend could branch on the
    reason itself rather than parsing message text — the same principle
    the frontend's MicrophoneErrorKind applies to microphone failures.
    """

    UNSUPPORTED_FORMAT = "unsupported_format"
    FILE_TOO_LARGE = "file_too_large"
    EMPTY_FILE = "empty_file"


class AudioValidationError(Exception):
    """
    Raised the moment an uploaded file fails validation, before anything
    is written to storage or recorded. Carries both the machine-readable
    `reason` and a friendly `message` safe to show a user directly.
    """

    def __init__(self, reason: AudioValidationReason, message: str) -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)
