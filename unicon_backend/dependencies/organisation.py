from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlmodel import Session

from unicon_backend.dependencies.auth import get_db_session
from unicon_backend.models.organisation import Organisation


def get_organisation_by_id(
    id: int,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> Organisation:
    organisation = db_session.get(Organisation, id)
    if organisation is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Organisation not found")
    return organisation
