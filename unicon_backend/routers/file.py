import mimetypes
import pathlib

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from minio import S3Error  # type: ignore

from unicon_backend.constants import MINIO_BUCKET
from unicon_backend.dependencies.auth import get_current_user
from unicon_backend.lib.file import download_file, get_valid_key, upload_file

router = APIRouter(prefix="/files", tags=["file"], dependencies=[Depends(get_current_user)])


@router.post("", response_model=str)
async def create_file(file: UploadFile):
    content_type = mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    ext = pathlib.Path(file.filename).suffix if file.filename else ""
    key = get_valid_key(ext)
    upload_file(MINIO_BUCKET, key, await file.read(), content_type)
    return key


@router.get("/{file_id}")
async def get_file(file_id: str):
    try:
        file = download_file(MINIO_BUCKET, file_id)
    except S3Error as err:
        raise HTTPException(status_code=404, detail="File not found") from err

    return Response(
        content=file, media_type=mimetypes.guess_type(file_id)[0] or "application/octet-stream"
    )
