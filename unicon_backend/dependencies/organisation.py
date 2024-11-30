from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlmodel import Session

from unicon_backend.dependencies.auth import get_current_user, get_db_session
from unicon_backend.models.organisation import Organisation
from unicon_backend.models.user import UserORM


def get_organisation_by_id(
    id: int,
    db_session: Annotated[Session, Depends(get_db_session)],
    user: Annotated[UserORM, Depends(get_current_user)],
) -> Organisation:
    organisation = db_session.get(Organisation, id)
    if organisation is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Organisation not found")
    if organisation.owner_id != user.id:
        raise HTTPException(HTTPStatus.FORBIDDEN, "User is not the owner of the organisation")
    return organisation
