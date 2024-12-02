from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from unicon_backend.dependencies.auth import get_current_user
from unicon_backend.dependencies.common import get_db_session
from unicon_backend.models.organisation import InvitationKey, Project, Role, RoleBase
from unicon_backend.models.user import UserORM

router = APIRouter(prefix="/roles", tags=["role"], dependencies=[Depends(get_current_user)])


@router.put("/{id}", summary="Update a role")
def update_role(
    id: int,
    user: Annotated[UserORM, Depends(get_current_user)],
    db_session: Annotated[Session, Depends(get_db_session)],
    role_data: RoleBase,
):
    role = db_session.get(Role, id)
    if role is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Role not found")

    # TODO: fix permissions
    if role.project.organisation.owner_id != user.id:
        raise HTTPException(HTTPStatus.FORBIDDEN, "User is not the owner of the organisation")

    role.sqlmodel_update(role_data)
    db_session.commit()
    db_session.refresh(role)
    return role


@router.delete("/{id}", summary="Delete a role")
def delete_role(
    id: int,
    user: Annotated[UserORM, Depends(get_current_user)],
    db_session: Annotated[Session, Depends(get_db_session)],
):
    role = db_session.get(Role, id)
    if role is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Role not found")

    # TODO: fix permissions
    if role.project.organisation.owner_id != user.id:
        raise HTTPException(HTTPStatus.FORBIDDEN, "User is not the owner of the organisation")

    if role.users:
        raise HTTPException(HTTPStatus.CONFLICT, "Role still has users")

    db_session.delete(role)
    db_session.commit()
    return


# NOTE: Only 1 active invitation_key allowed at a time


@router.post("/{id}/invitation_key", summary="Create invitation key")
def create_invitation_key(
    id: int,
    user: Annotated[UserORM, Depends(get_current_user)],
    db_session: Annotated[Session, Depends(get_db_session)],
):
    role = db_session.exec(
        select(Role)
        .where(Role.id == id)
        .options(
            selectinload(Role.project).selectinload(Project.organisation),
            selectinload(Role.invitation_keys),
        )
    ).first()

    if role is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Role not found")

    # TODO: fix permissions
    if role.project.organisation.owner_id != user.id:
        raise HTTPException(HTTPStatus.FORBIDDEN, "User is not the owner of the organisation")

    if any(invitation_key.enabled for invitation_key in role.invitation_keys):
        raise HTTPException(HTTPStatus.CONFLICT, "Role already has an active invitation key")

    invitation_key = InvitationKey(role_id=role.id)
    db_session.add(invitation_key)
    db_session.commit()
    db_session.refresh(invitation_key)
    return invitation_key


@router.delete("/{id}/invitation_key", summary="Disable an invitation key")
def delete_invitation_key(
    id: int,
    user: Annotated[UserORM, Depends(get_current_user)],
    db_session: Annotated[Session, Depends(get_db_session)],
):
    role: Role = db_session.exec(
        select(Role)
        .where(Role.id == id)
        .options(
            selectinload(Role.project).selectinload(Project.organisation),
            selectinload(Role.invitation_keys),
        )
    ).first()

    if role is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Role not found")

    if role.project.organisation.owner_id != user.id:
        raise HTTPException(HTTPStatus.FORBIDDEN, "User is not the owner of the organisation")

    enabled_keys: list[InvitationKey] = [
        invitation_key for invitation_key in role.invitation_keys if invitation_key.enabled
    ]
    if not enabled_keys:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Role does not have an active invitation key")

    for invitation_key in enabled_keys:
        invitation_key.enabled = False
        db_session.add(invitation_key)

    db_session.commit()
    return
