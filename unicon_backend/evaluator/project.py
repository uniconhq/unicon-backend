from pydantic import BaseModel, SerializeAsAny

from unicon_backend.evaluator.tasks.base import Task
from unicon_backend.evaluator.tasks.programming import ProgrammingTask
from unicon_backend.evaluator.answer import Answer


class Project(BaseModel):
    name: str
    description: str
    tasks: list[SerializeAsAny[Task]]

    def run(self, answer: Answer):
        for task in self.tasks:
            if isinstance(task, ProgrammingTask):
                task.run(answer)
