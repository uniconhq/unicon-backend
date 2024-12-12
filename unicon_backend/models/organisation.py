import uuid
from typing import TYPE_CHECKING

import sqlalchemy.orm as sa_orm
from sqlmodel import Field, Relationship

from unicon_backend.lib.common import CustomSQLModel
from unicon_backend.models.links import UserRole

if TYPE_CHECKING:
    from .contest import ProblemORM
    from .user import UserORM


class OrganisationBase(CustomSQLModel):
    name: str
    description: str


class Organisation(OrganisationBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    owner_id: int | None = Field(foreign_key="user.id", nullable=False)
    projects: sa_orm.Mapped[list["Project"]] = Relationship(back_populates="organisation")


class ProjectBase(CustomSQLModel):
    name: str


class Project(ProjectBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    organisation_id: int | None = Field(foreign_key="organisation.id", nullable=False)

    organisation: sa_orm.Mapped[Organisation] = Relationship(back_populates="projects")
    roles: sa_orm.Mapped[list["Role"]] = Relationship(back_populates="project")
    problems: sa_orm.Mapped[list["ProblemORM"]] = Relationship(back_populates="project")


class RoleBase(CustomSQLModel):
    name: str


class Role(RoleBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")

    project: sa_orm.Mapped[Project] = Relationship(back_populates="roles")
    invitation_keys: sa_orm.Mapped[list["InvitationKey"]] = Relationship(back_populates="role")

    users: sa_orm.Mapped[list["UserORM"]] = Relationship(
        back_populates="roles", link_model=UserRole
    )


class InvitationKeyBase(CustomSQLModel):
    key: uuid.UUID = Field(default_factory=uuid.uuid4, unique=True)
    enabled: bool = Field(default=True)


class InvitationKey(InvitationKeyBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    role_id: int = Field(foreign_key="role.id")

    role: sa_orm.Mapped[Role] = Relationship(back_populates="invitation_keys")
