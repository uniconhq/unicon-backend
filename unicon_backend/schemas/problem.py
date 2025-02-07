from pydantic import BaseModel


class ParseRequest(BaseModel):
    content: str
