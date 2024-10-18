from pydantic import BaseModel


class File(BaseModel):
    file_name: str
    content: str
