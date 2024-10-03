from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from unicon_backend.constants import SECRET_KEY, sql_engine
from unicon_backend.dependencies import AUTH_ALGORITHM, AUTH_PWD_CONTEXT, get_current_user
from unicon_backend.models import User

ACCESS_TOKEN_EXPIRE_MINUTES = 30

router = APIRouter(prefix="/auth", tags=["auth"])


def create_access_token(data: dict, expires_delta: timedelta) -> str:
    return jwt.encode(
        {**data, "exp": datetime.now(UTC) + expires_delta}, SECRET_KEY, algorithm=AUTH_ALGORITHM
    )


def authenticate_user(username: str, password: str) -> User | None:
    with Session(sql_engine) as session:
        user: User | None = session.scalars(select(User).where(User.username == username)).first()
        # NOTE: user.password is the hashed password
        return (
            user if user is not None and AUTH_PWD_CONTEXT.verify(password, user.password) else None
        )


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserPublic


@router.post("/token")
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], response: Response):
    if (user := authenticate_user(form_data.username, form_data.password)) is None:
        raise HTTPException(status_code=400, detail="Incorrect username or password.")

    user_public = UserPublic.model_validate(user)
    access_token = create_access_token(
        data={"sub": user.id}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    response.set_cookie(key="session", value=access_token)

    return Token(access_token=access_token, token_type="bearer", user=user_public)


@router.get("/session")
def get_user(user: Annotated[User, Depends(get_current_user)]) -> UserPublic:
    return UserPublic.model_validate(user)
