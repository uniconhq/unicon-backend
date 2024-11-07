from sqlmodel import Field, SQLModel


class UserORM(SQLModel, table=True):
    __tablename__ = "user"

    id: int = Field(primary_key=True)
    username: str
    password: str
