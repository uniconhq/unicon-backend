from pydantic import BaseModel

from unicon_backend.evaluator.tasks.base import Task


class Project(BaseModel):
    name: str
    description: str
    tasks: list[Task]
