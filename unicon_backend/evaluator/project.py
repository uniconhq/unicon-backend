from pydantic import BaseModel, SerializeAsAny

from unicon_backend.evaluator.tasks.base import Task


class Project(BaseModel):
    name: str
    description: str
    tasks: list[SerializeAsAny[Task]]
