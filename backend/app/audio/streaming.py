from typing import Awaitable, Callable

from .errors import AudioValidationError, AudioValidationReason

_CHUNK_SIZE = 1024 * 1024  # 1 MiB per read


async def read_within_limit(read: Callable[[int], Awaitable[bytes]], max_bytes: int) -> bytes:
    """
    Reads a stream in fixed-size chunks, raising as soon as the running
    total exceeds `max_bytes` — never buffering more than roughly one
    chunk past the limit in memory.

    Enforced this way rather than trusting the request's Content-Length
    header, because a client can send whatever Content-Length it wants;
    only counting the bytes actually received is reliable. This matters
    for a "production quality" upload handler: naively calling
    `await file.read()` unbounded would let a client exhaust server
    memory with an oversized upload before validation ever runs.
    """
    total = 0
    chunks: list[bytes] = []

    while True:
        chunk = await read(_CHUNK_SIZE)
        if not chunk:
            break

        total += len(chunk)
        if total > max_bytes:
            raise AudioValidationError(
                AudioValidationReason.FILE_TOO_LARGE,
                f"Files must be {max_bytes // (1024 * 1024)} MB or smaller.",
            )
        chunks.append(chunk)

    return b"".join(chunks)
