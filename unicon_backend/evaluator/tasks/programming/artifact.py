from pydantic import BaseModel

PrimitiveData = str | int | float | bool


class File(BaseModel):
    file_name: str
    content: str
