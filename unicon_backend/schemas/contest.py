from pydantic import BaseModel


class BaseDefinitionDTO(BaseModel):
    id: int
    name: str
    description: str
