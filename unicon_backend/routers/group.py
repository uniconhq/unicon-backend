from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col

from unicon_backend.dependencies.auth import get_current_user
from unicon_backend.dependencies.common import get_db_session
from unicon_backend.dependencies.group import get_group_by_id
from unicon_backend.lib.permissions.permission import (
    permission_check,
    permission_delete,
    permission_update,
)
from unicon_backend.models.links import GroupMember
from unicon_backend.models.organisation import Group
from unicon_backend.models.user import UserORM
from unicon_backend.schemas.group import GroupPublic, GroupUpdate

router = APIRouter(prefix="/groups", tags=["groups"], dependencies=[Depends(get_current_user)])


@router.get("/{id}", summary="Get a group", response_model=GroupPublic)
def get_group(
    group: Annotated[Group, Depends(get_group_by_id)],
    user: Annotated[UserORM, Depends(get_current_user)],
):
    if not permission_check(group, "view", user):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Permission denied")

    return group


@router.put("/{id}", summary="Update a group", response_model=GroupPublic)
def update_group(
    group: Annotated[Group, Depends(get_group_by_id)],
    data: GroupUpdate,
    db_session: Annotated[Session, Depends(get_db_session)],
    user: Annotated[UserORM, Depends(get_current_user)],
):
    if not permission_check(group, "edit", user):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Permission denied")

    old_group = group.model_copy(deep=True)

    group.name = data.name
    users = db_session.scalars(
        select(UserORM)
        .where(col(UserORM.id).in_(data.members + data.supervisors))
        .options(selectinload(UserORM.roles))
    ).all()

    if len(users) != len(data.members + data.supervisors):
        raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, "Some users do not exist")

    if any([not any(role.project_id == group.project_id for role in user.roles) for user in users]):
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY, "Some users do not belong to the group's project"
        )

    group.members.clear()
    group.members = [
        GroupMember(user_id=user.id, is_supervisor=False)
        for user in users
        if user.id in data.members
    ] + [
        GroupMember(user_id=user.id, is_supervisor=True)
        for user in users
        if user.id in data.supervisors
    ]

    db_session.commit()
    db_session.refresh(group)

    permission_update(old_group, group)

    return group


@router.delete("/{id}", summary="Delete a group")
def delete_group(
    db_session: Annotated[Session, Depends(get_db_session)],
    group: Annotated[Group, Depends(get_group_by_id)],
    user: Annotated[UserORM, Depends(get_current_user)],
):
    if not permission_check(group, "delete", user):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Permission denied")

    old_group = group.model_copy(deep=True)

    group.members.clear()
    db_session.delete(group)
    db_session.commit()
    permission_delete(old_group)
