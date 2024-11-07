from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from unicon_backend.constants import SECRET_KEY
from unicon_backend.dependencies import (
    AUTH_ALGORITHM,
    AUTH_PWD_CONTEXT,
    get_current_user,
    get_db_session,
)
from unicon_backend.models import UserORM

ACCESS_TOKEN_EXPIRE_MINUTES = 30

router = APIRouter(prefix="/auth", tags=["auth"])


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserPublic


@router.post("/token")
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db_session: Annotated[Session, Depends(get_db_session)],
    response: Response,
) -> Token:
    # NOTE: `password` is hashed
    username, password = form_data.username, form_data.password

    user: UserORM | None = db_session.scalars(
        select(UserORM).where(UserORM.username == username)
    ).first()
    if user is None or not AUTH_PWD_CONTEXT.verify(password, user.password):
        raise HTTPException(status_code=400, detail="Incorrect username or password.")

    user_public = UserPublic.model_validate(user)
    access_token: str = jwt.encode(
        {"sub": user.id, "exp": datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)},
        SECRET_KEY,
        algorithm=AUTH_ALGORITHM,
    )
    response.set_cookie(key="session", value=access_token)

    return Token(access_token=access_token, token_type="bearer", user=user_public)


@router.get("/logout")
def logout(response: Response):
    response.delete_cookie(key="session")
    return ""


@router.get("/session")
def get_user(user: Annotated[UserORM, Depends(get_current_user)]) -> UserPublic:
    return UserPublic.model_validate(user)
