from typing import TYPE_CHECKING

import sqlalchemy.orm as sa_orm
from sqlmodel import Field, Relationship

from unicon_backend.lib.common import CustomSQLModel
from unicon_backend.models.links import UserRole

if TYPE_CHECKING:
    from unicon_backend.models.organisation import Role
    from unicon_backend.models.problem import SubmissionORM


class UserORM(CustomSQLModel, table=True):
    __tablename__ = "user"

    id: int = Field(primary_key=True)
    username: str = Field(unique=True, index=True)
    password: str

    roles: sa_orm.Mapped[list["Role"]] = Relationship(back_populates="users", link_model=UserRole)

    submissions: sa_orm.Mapped[list["SubmissionORM"]] = Relationship(back_populates="user")
