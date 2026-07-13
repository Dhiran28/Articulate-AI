from fastapi import UploadFile

from .base import RawAudioUpload


class HttpUploadIngestor:
    """
    Wraps a FastAPI/Starlette UploadFile — a multipart file field on
    POST /api/audio — as a RawAudioUpload. Today's only AudioIngestor; see
    base.py for why this is an interface rather than AudioService calling
    UploadFile directly.
    """

    def __init__(self, upload_file: UploadFile) -> None:
        self._upload_file = upload_file

    async def ingest(self) -> RawAudioUpload:
        return RawAudioUpload(
            filename=self._upload_file.filename or "unnamed",
            content_type=self._upload_file.content_type,
            read=self._upload_file.read,
        )
