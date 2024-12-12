from pydantic import BaseModel, ConfigDict, model_validator
from sqlmodel import Field

from unicon_backend.lib.common import CustomSQLModel
from unicon_backend.schemas.organisation import RolePublic


class UserCreate(CustomSQLModel):
    username: str
    password: str = Field(min_length=8)
    confirm_password: str

    @model_validator(mode="after")
    def check_password_match(self):
        if self.password != self.confirm_password:
            raise ValueError("passwords do not match")
        return self


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserPublic


class UserPublicWithRoles(CustomSQLModel):
    id: int
    username: str
    roles: list[RolePublic]
