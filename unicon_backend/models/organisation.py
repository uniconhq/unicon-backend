import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
import sqlalchemy.orm as sa_orm
from sqlmodel import Field, Relationship

from unicon_backend.lib.common import CustomSQLModel
from unicon_backend.models.links import GroupMember, UserRole

if TYPE_CHECKING:
    from unicon_backend.models.problem import ProblemORM
    from unicon_backend.models.user import UserORM


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
    problems: sa_orm.Mapped[list["ProblemORM"]] = Relationship(
        back_populates="project", sa_relationship_kwargs={"order_by": "ProblemORM.id.desc()"}
    )


class RoleBase(CustomSQLModel):
    name: str


class Role(RoleBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")

    # Assignable permissions
    view_problems_access: bool = Field(
        default=False,
        sa_column=sa.Column(sa.Boolean(), server_default="0"),
    )
    create_problems_access: bool = Field(
        default=False,
        sa_column=sa.Column(sa.Boolean(), server_default="0"),
    )
    edit_problems_access: bool = Field(
        default=False,
        sa_column=sa.Column(sa.Boolean(), server_default="0"),
    )
    delete_problems_access: bool = Field(
        default=False,
        sa_column=sa.Column(sa.Boolean(), server_default="0"),
    )
    view_restricted_problems_access: bool = Field(
        default=False,
        sa_column=sa.Column(sa.Boolean(), server_default="0"),
    )
    edit_restricted_problems_access: bool = Field(
        default=False,
        sa_column=sa.Column(sa.Boolean(), server_default="0"),
    )
    delete_restricted_problems_access: bool = Field(
        default=False,
        sa_column=sa.Column(sa.Boolean(), server_default="0"),
    )
    make_submission_access: bool = Field(
        default=False,
        sa_column=sa.Column(sa.Boolean(), server_default="0"),
    )
    view_own_submissions_access: bool = Field(
        default=False,
        sa_column=sa.Column(sa.Boolean(), server_default="0"),
    )
    view_others_submission_access: bool = Field(
        default=False,
        sa_column=sa.Column(sa.Boolean(), server_default="0"),
    )

    project: sa_orm.Mapped[Project] = Relationship(back_populates="roles")
    invitation_keys: sa_orm.Mapped[list["InvitationKey"]] = Relationship(back_populates="role")

    users: sa_orm.Mapped[list["UserORM"]] = Relationship(
        back_populates="roles", link_model=UserRole
    )


class GroupType(CustomSQLModel):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    name: str


class Group(CustomSQLModel):
    id: int | None = Field(default=None, primary_key=True)
    group_type_id: int = Field(foreign_key="group_type.id")
    supervisor_id: int = Field(foreign_key="user.id")

    # todo: check if this breaks since there are 2 relations to user
    supervisor: sa_orm.Mapped["UserORM"] = Relationship(back_populates="supervised_groups")

    members: sa_orm.Mapped[list["GroupMember"]] = Relationship(
        back_populates="group", link_model=GroupMember
    )


class InvitationKeyBase(CustomSQLModel):
    key: uuid.UUID = Field(default_factory=uuid.uuid4, unique=True)
    enabled: bool = Field(default=True)


class InvitationKey(InvitationKeyBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    role_id: int = Field(foreign_key="role.id")

    role: sa_orm.Mapped[Role] = Relationship(back_populates="invitation_keys")
