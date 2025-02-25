import mimetypes
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from minio import S3Error  # type: ignore
from sqlalchemy import select
from sqlmodel import Session, col

from unicon_backend.constants import MINIO_BUCKET
from unicon_backend.dependencies.auth import get_current_user
from unicon_backend.dependencies.common import get_db_session
from unicon_backend.lib.file import download_file, upload_fastapi_file
from unicon_backend.models.file import FileORM

router = APIRouter(prefix="/files", tags=["file"], dependencies=[Depends(get_current_user)])


@router.post("", response_model=str)
async def create_file(file: UploadFile):
    return upload_fastapi_file(file)


@router.get("/{file_id}")
async def get_file(file_id: str, db_session: Annotated[Session, Depends(get_db_session)]):
    try:
        file = download_file(MINIO_BUCKET, file_id)
    except S3Error as err:
        raise HTTPException(status_code=404, detail="File not found") from err

    # Files within programming tasks are currently not in the FileORM table.
    fileOrm = db_session.scalar(select(FileORM).where(col(FileORM.key) == file_id))
    name = fileOrm.path.split("/")[-1] if fileOrm else file_id

    return Response(
        # This header is necessary for cross-origin downloads.
        # Reference: https://macarthur.me/posts/trigger-cross-origin-download/
        headers={"Content-Disposition": f"attachment; filename={name}"},
        content=file,
        media_type=mimetypes.guess_type(file_id)[0] or "application/octet-stream",
    )
