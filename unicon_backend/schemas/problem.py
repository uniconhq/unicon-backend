from pydantic import BaseModel


class ParseRequest(BaseModel):
    content: str


class ParsedFunction(BaseModel):
    name: str
    args: list[str]
    kwargs: list[str]
    star_args: bool
    star_kwargs: bool
