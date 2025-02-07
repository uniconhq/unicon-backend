"""
This file exists because of the otherwise existing circular dependency between user and role files for the link_model.
"""

from typing import TYPE_CHECKING

import sqlalchemy.orm as sa_orm
from sqlmodel import Field, Relationship

from unicon_backend.lib.common import CustomSQLModel

if TYPE_CHECKING:
    from unicon_backend.models.organisation import Group
    from unicon_backend.models.user import UserORM


class UserRole(CustomSQLModel, table=True):
    __tablename__ = "user_role"

    user_id: int = Field(foreign_key="user.id", primary_key=True)
    role_id: int = Field(foreign_key="role.id", primary_key=True)


class GroupMember(CustomSQLModel, table=True):
    __tablename__ = "group_member"

    user_id: int = Field(foreign_key="user.id", primary_key=True)
    group_id: int = Field(foreign_key="group.id", primary_key=True)
    is_supervisor: bool = Field(default=False, sa_column_kwargs={"server_default": "0"})

    group: sa_orm.Mapped["Group"] = Relationship(back_populates="members")
    user: sa_orm.Mapped["UserORM"] = Relationship(back_populates="group_members")
