from pathlib import Path

from .errors import AudioValidationError, AudioValidationReason
from .models import AudioFormat

_UNSUPPORTED_FORMAT_MESSAGE = "Only .wav, .mp3, .m4a, and .webm files are supported."

# Extension -> the set of Content-Type values browsers/OSes are known to
# send for that extension. Deliberately permissive: the same extension is
# reported with different MIME types across browsers and operating
# systems (e.g. .m4a shows up as "audio/mp4" in some places and
# "audio/x-m4a" in others), so pairing extension to one exact
# content-type would reject legitimate files.
_ALLOWED_CONTENT_TYPES: dict[AudioFormat, set[str]] = {
    "wav": {"audio/wav", "audio/x-wav", "audio/wave"},
    "mp3": {"audio/mpeg", "audio/mp3"},
    "m4a": {"audio/mp4", "audio/x-m4a", "audio/m4a"},
    "webm": {"audio/webm"},
}

# Some OS file pickers report a generic or missing content-type for audio
# files. When that happens, we fall back to trusting the extension alone
# rather than rejecting a legitimate file over an uninformative header.
_GENERIC_CONTENT_TYPES = {"application/octet-stream", "", None}


def validate_format(filename: str, content_type: str | None) -> AudioFormat:
    """
    Confirms `filename`'s extension is one of the four supported formats,
    and — when the browser/OS supplied a specific, non-generic
    content-type — that it's consistent with that extension.

    This is NOT a guarantee the file's actual bytes are what its name and
    header claim. That would require inspecting the file's contents
    (magic-byte sniffing), which is deliberately not implemented this
    sprint — the same "flag it, don't build it" treatment ADR 002 gives
    its other open questions. What this catches: accidental wrong file
    types and obviously unsupported formats. What it doesn't catch: a
    file deliberately renamed to spoof one of the four extensions.
    """
    suffix = Path(filename).suffix.lower().lstrip(".")

    if suffix not in _ALLOWED_CONTENT_TYPES:
        raise AudioValidationError(AudioValidationReason.UNSUPPORTED_FORMAT, _UNSUPPORTED_FORMAT_MESSAGE)

    audio_format: AudioFormat = suffix  # type: ignore[assignment]

    if content_type not in _GENERIC_CONTENT_TYPES and content_type not in _ALLOWED_CONTENT_TYPES[audio_format]:
        raise AudioValidationError(AudioValidationReason.UNSUPPORTED_FORMAT, _UNSUPPORTED_FORMAT_MESSAGE)

    return audio_format
