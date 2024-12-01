from pydantic import model_validator
from sqlmodel import Field, SQLModel


class UserCreate(SQLModel):
    username: str
    password: str = Field(min_length=8)
    confirm_password: str

    @model_validator(mode="after")
    def check_password_match(self):
        if self.password != self.confirm_password:
            raise ValueError("passwords do not match")
        return self
