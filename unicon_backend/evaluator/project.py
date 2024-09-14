from pydantic import BaseModel, RootModel, SerializeAsAny
from typing import Any

from unicon_backend.evaluator.tasks.base import Task


class Answer(BaseModel):
    id: int
    expected: Any


class ProjectAnswers(RootModel):
    root: list[Answer]

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]


class Project(BaseModel):
    name: str
    description: str
    tasks: list[SerializeAsAny[Task]]

    def run(self, answers: ProjectAnswers):
        answer_index: dict[int, Answer] = {
            task_answer.id: task_answer for task_answer in answers
        }

        for task in self.tasks:
            if (task_answer := answer_index.get(task.id)) is None:
                print(f"WARN: Task {task.id} has no answer")
                continue

            _task_out = task.run(task.validate_answer(task_answer.expected))
            print(f"Task {task.id} output: {_task_out}")
