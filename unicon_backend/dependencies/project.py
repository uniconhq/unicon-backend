from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from unicon_backend.dependencies.auth import get_current_user
from unicon_backend.dependencies.common import get_db_session
from unicon_backend.models.organisation import Project, Role
from unicon_backend.models.user import UserORM
from unicon_backend.schemas.organisation import ProjectCreate

OWNER_ROLE = "Owner"
DEFAULT_ROLES = [OWNER_ROLE, "Helper", "Member"]


def create_project_with_defaults(
    create_data: ProjectCreate, organisation_id: int, user: UserORM
) -> Project:
    new_project = Project.model_validate(
        {**create_data.model_dump(), "organisation_id": organisation_id}
    )

    # Create three default roles
    roles = [Role(name=role_name, project=new_project) for role_name in DEFAULT_ROLES]
    new_project.roles = roles
    adminstrator_role = roles[0]

    # Make owner admin
    user.roles.append(adminstrator_role)

    # TODO: add permission to roles

    return new_project


def get_project_by_id(
    id: int,
    db_session: Annotated[Session, Depends(get_db_session)],
    user: Annotated[UserORM, Depends(get_current_user)],
) -> Project:
    project = db_session.exec(
        select(Project)
        .join(Role)
        .where(Project.id == id)
        .options(
            selectinload(Project.roles.and_(Role.users.contains(user))).selectinload(
                Role.invitation_keys
            )
        )
    ).first()

    if project is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Project not found")

    return project
