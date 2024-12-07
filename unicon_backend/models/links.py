"""
This file exists because of the otherwise existing circular dependency between user and role files for the link_model.
"""

import sqlalchemy.orm as sa_orm
from sqlmodel import Field, SQLModel


class UserRole(SQLModel, table=True):
    user_id: sa_orm.Mapped[int] = Field(foreign_key="user.id", primary_key=True)
    role_id: sa_orm.Mapped[int] = Field(foreign_key="role.id", primary_key=True)
