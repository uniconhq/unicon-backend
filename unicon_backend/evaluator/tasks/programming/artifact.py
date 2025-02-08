from pydantic import BaseModel

PrimitiveData = str | int | float | bool


class File(BaseModel):
    name: str
    content: str

    trusted: bool = False
