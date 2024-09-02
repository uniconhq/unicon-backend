from typing import Annotated


from datetime import timedelta
from fastapi import Depends, APIRouter, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm

from pydantic import BaseModel, ConfigDict

from ..dependencies.auth import ACCESS_TOKEN_EXPIRE_MINUTES, authenticate_user, create_access_token, get_current_user
from ..models import User

router = APIRouter(prefix="/auth")


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
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=400, detail="Incorrect username or password.")
    user_public = UserPublic.model_validate(user)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )

    response.set_cookie(key="session", value=access_token)
    return Token(access_token=access_token, token_type="bearer", user=user_public)


@router.get("/session")
def get_user(staff: Annotated[User, Depends(get_current_user)]) -> UserPublic:
    return staff
