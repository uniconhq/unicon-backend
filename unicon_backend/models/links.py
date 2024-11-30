"""
This file exists because of the otherwise existing circular dependency between user and role files for the link_model.
"""

from sqlmodel import Field, SQLModel


class UserRole(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    role_id: int = Field(foreign_key="role.id", primary_key=True)
