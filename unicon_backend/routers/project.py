from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from unicon_backend.dependencies.auth import get_current_user
from unicon_backend.dependencies.common import get_db_session
from unicon_backend.models.links import UserRole
from unicon_backend.models.organisation import Project, Role
from unicon_backend.models.user import UserORM
from unicon_backend.schemas.organisation import ProjectPublic, ProjectUpdate

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
        .options(selectinload(Project.roles.and_(Role.users.contains(user))))
    ).all()

    return projects


@router.get("/{id}", summary="Get a project", response_model=ProjectPublic)
def get_project(
    id: int,
    db_session: Annotated[Session, Depends(get_db_session)],
    user: Annotated[UserORM, Depends(get_current_user)],
):
    project = db_session.exec(
        select(Project)
        .join(Role)
        .join(UserRole)
        .where(UserRole.user_id == user.id)
        .where(Project.id == id)
        .options(selectinload(Project.roles.and_(Role.users.contains(user))))
    ).first()

    if project is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Project not found")

    return project


@router.put("/{id}", summary="Update a project", response_model=ProjectPublic)
def update_project(
    id: int,
    db_session: Annotated[Session, Depends(get_db_session)],
    user: Annotated[UserORM, Depends(get_current_user)],
    update_data: ProjectUpdate,
):
    project = db_session.exec(
        select(Project)
        .join(Role)
        .join(UserRole)
        .where(UserRole.user_id == user.id)
        .where(Project.id == id)
        .options(selectinload(Project.roles.and_(Role.users.contains(user))))
    ).first()

    if project is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Project not found")

    # TODO: Add permissions here - currently just checking if user is part of project

    project.sqlmodel_update(update_data)
    db_session.commit()
    db_session.refresh(project)
    return project
