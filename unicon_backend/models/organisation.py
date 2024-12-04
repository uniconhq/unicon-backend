import uuid
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from unicon_backend.models.links import UserRole

if TYPE_CHECKING:
    from .contest import ProblemORM
    from .user import UserORM


class OrganisationBase(SQLModel):
    name: str
    description: str


class Organisation(OrganisationBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    owner_id: int | None = Field(foreign_key="user.id", nullable=False)
    projects: list["Project"] = Relationship(back_populates="organisation")


class ProjectBase(SQLModel):
    name: str


class Project(ProjectBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    organisation_id: int | None = Field(foreign_key="organisation.id", nullable=False)

    organisation: Organisation = Relationship(back_populates="projects")
    roles: list["Role"] = Relationship(back_populates="project")
    problems: list["ProblemORM"] = Relationship(back_populates="project")


class RoleBase(SQLModel):
    name: str


class Role(RoleBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")

    project: Project = Relationship(back_populates="roles")
    invitation_keys: list["InvitationKey"] = Relationship(back_populates="role")

    users: list["UserORM"] = Relationship(back_populates="roles", link_model=UserRole)


class InvitationKeyBase(SQLModel):
    key: uuid.UUID = Field(default_factory=uuid.uuid4, unique=True)
    enabled: bool = Field(default=True)


class InvitationKey(InvitationKeyBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    role_id: int = Field(foreign_key="role.id")

    role: Role = Relationship(back_populates="invitation_keys")
