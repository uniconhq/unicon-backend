from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from sqlmodel import Session

from unicon_backend.constants import SECRET_KEY
from unicon_backend.database import SessionLocal
from unicon_backend.models import UserORM

AUTH_ALGORITHM = "HS256"
AUTH_PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


class OAuth2IgnoreError(OAuth2PasswordBearer):
    """Ignore HTTP error because we want to accept cookie auth too"""

    async def __call__(self, request: Request) -> str | None:
        try:
            return await super().__call__(request)
        except HTTPException:
            return ""


OAUTH2_SCHEME = OAuth2IgnoreError(tokenUrl="/auth/token")


def get_db_session():
    with SessionLocal() as session:
        yield session


async def get_current_user(
    token: Annotated[str | None, Depends(OAUTH2_SCHEME)],
    db_session: Annotated[Session, Depends(get_db_session)],
    session: Annotated[str | None, Cookie()] = None,
) -> UserORM:
    if (token := token or session) is None:
        raise HTTPException(401, "No authentication token provided")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[AUTH_ALGORITHM])
        id = payload.get("sub")
        if (user := db_session.get(UserORM, id)) is None:
            raise InvalidTokenError()
        return user

    except InvalidTokenError as invalid_token_err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from invalid_token_err
