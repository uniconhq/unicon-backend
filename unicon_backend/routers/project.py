from http import HTTPStatus
from typing import Annotated

import sqlalchemy
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import selectinload
from sqlmodel import Session, and_, select

from unicon_backend.dependencies.auth import get_current_user
from unicon_backend.dependencies.common import get_db_session
from unicon_backend.dependencies.project import get_project_by_id
from unicon_backend.evaluator.contest import Definition
from unicon_backend.models.contest import ProblemORM
from unicon_backend.models.links import UserRole
from unicon_backend.models.organisation import InvitationKey, Project, Role
from unicon_backend.models.user import UserORM
from unicon_backend.schemas.auth import UserPublicWithRoles
from unicon_backend.schemas.organisation import (
    ProjectPublic,
    ProjectPublicWithProblems,
    ProjectUpdate,
    RoleCreate,
    RolePublic,
    RolePublicWithInvitationKeys,
)

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(get_current_user)])


@router.get("/", summary="Get all projects user is part of", response_model=list[ProjectPublic])
def get_all_projects(
    user: Annotated[UserORM, Depends(get_current_user)],
    db_session: Annotated[Session, Depends(get_db_session)],
):
    projects = db_session.exec(
        select(Project)
        .join(Role)
        .join(UserRole)
        .where(UserRole.user_id == user.id)
        .where(UserRole.role_id == Role.id)
        .options(selectinload(Project.roles.and_(Role.users.any(UserORM.id == user.id))))
    ).all()

    return projects


@router.get("/{id}", summary="Get a project", response_model=ProjectPublicWithProblems)
def get_project(
    project: Annotated[Project, Depends(get_project_by_id)],
):
    return project


@router.put("/{id}", summary="Update a project", response_model=ProjectPublic)
def update_project(
    db_session: Annotated[Session, Depends(get_db_session)],
    update_data: ProjectUpdate,
    project: Annotated[Project, Depends(get_project_by_id)],
):
    # TODO: Add permissions here - currently just checking if user is part of project

    project.sqlmodel_update(update_data)
    db_session.commit()
    db_session.refresh(project)
    return project


@router.get(
    "/{id}/roles",
    summary="Get all roles in a project",
    response_model=list[RolePublicWithInvitationKeys],
)
def get_project_roles(
    id: int,
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[Project, Depends(get_project_by_id)],
):
    roles = db_session.exec(
        select(Role)
        .join(Project)
        .where(Project.id == id)
        .options(selectinload(Role.invitation_keys))
    ).all()

    return roles


@router.get(
    "/{id}/users", summary="Get all users in a project", response_model=list[UserPublicWithRoles]
)
def get_project_users(
    id: int,
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[Project, Depends(get_project_by_id)],
):
    users = db_session.exec(
        select(UserORM)
        .join(UserRole)
        .join(Role)
        .join(Project)
        .where(Project.id == id)
        .options(selectinload(UserORM.roles.and_(Role.project_id == id)))
    ).all()

    return users


@router.post("/{id}/roles", summary="Create a new role", response_model=RolePublic)
def create_role(
    id: int,
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[Project, Depends(get_project_by_id)],
    role_data: RoleCreate,
):
    role = Role(**role_data.model_dump())
    role.project_id = id
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


@router.post("/{key}/join", summary="Join project by invitation key", response_model=ProjectPublic)
def join_project(
    key: str,
    db_session: Annotated[Session, Depends(get_db_session)],
    user: Annotated[UserORM, Depends(get_current_user)],
):
    try:
        role = db_session.exec(
            select(Role)
            .join(Role.invitation_keys)
            .where(
                Role.invitation_keys.any(
                    and_(
                        InvitationKey.key == key,
                        InvitationKey.enabled == True,
                    )
                )
            )
        ).first()
    except sqlalchemy.exc.DataError:
        # invitation key is an invalid uuid
        role = None

    if role is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Invitation key not found")

    if role.project.organisation.owner_id == user.id:
        raise HTTPException(
            HTTPStatus.CONFLICT, "Owner cannot join project, they are already owner"
        )

    project_role_ids = [role.id for role in role.project.roles]
    user_role = db_session.exec(
        select(UserRole).where(
            and_(UserRole.user_id == user.id, UserRole.role_id.in_(project_role_ids))
        )
    ).first()

    if user_role:
        db_session.delete(user_role)

    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    db_session.commit()

    return role.project


@router.post("/{id}/problems")
def create_problem(
    definition: Definition,
    db_session: Annotated[Session, Depends(get_db_session)],
    project: Annotated[Project, Depends(get_project_by_id)],
) -> ProblemORM:
    # TODO: Add permissions here - currently just checking if project exists

    new_problem = ProblemORM.from_definition(definition)
    project.problems.append(new_problem)

    db_session.add(project)
    db_session.commit()
    db_session.refresh(new_problem)

    return new_problem
