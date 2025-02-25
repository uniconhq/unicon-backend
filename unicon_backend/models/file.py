from datetime import datetime, timedelta, timezone

from sqlmodel import Field

from unicon_backend.lib.common import CustomSQLModel

SGT = timezone(timedelta(hours=8))


class FileORM(CustomSQLModel, table=True):
    __tablename__ = "file"

    id: int | None = Field(default=None, primary_key=True)
    path: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(SGT))

    # File is a polymorphic model. It is expected we use this for more things in the future.
    # These fields can also be used for access control (permify).
    parent_id: int
    parent_type: str

    # Fields for files stored in minio. Refer to lib/file.py for functions to retrieve the file.
    on_minio: bool = Field(default=False)
    key: str

    # For the odd case where the file is not stored in minio.
    # Note: Binary files should always be stored in minio.
    content: str
