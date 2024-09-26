from typing import Any

from pydantic import BaseModel, RootModel, SerializeAsAny

from unicon_backend.evaluator.tasks.base import Task


class ExpectedAnswer(BaseModel):
    id: int
    expected_answer: Any


class UserInput(BaseModel):
    id: int
    user_input: Any


class ProjectExpectedAnswers(RootModel):
    root: list[ExpectedAnswer]

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]


class ProjectUserInputs(RootModel):
    root: list[UserInput]

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]


class Project(BaseModel):
    name: str
    description: str
    tasks: list[SerializeAsAny[Task]]

    def run(
        self,
        user_inputs: ProjectUserInputs,
        expected_answers: ProjectExpectedAnswers,
        task_id: int | None = None,
    ):
        user_input_index: dict[int, UserInput] = {
            task_input.id: task_input for task_input in user_inputs
        }
        expected_answer_index: dict[int, ExpectedAnswer] = {
            task_answer.id: task_answer for task_answer in expected_answers
        }

        tasks_to_run = (
            self.tasks
            if task_id is None
            else [task for task in self.tasks if task.id == task_id]
        )

        for task in tasks_to_run:
            if (task_user_input := user_input_index.get(task.id)) is None:
                print(f"WARN: Task {task.id} has no user input")
                continue

            if (task_expected_answer := expected_answer_index.get(task.id)) is None:
                print(f"WARN: Task {task.id} has no answer")
                continue

            print(f"Running task {task.id}")

            _task_out = task.run(
                task.validate_user_input(task_user_input.user_input),
                task.validate_expected_answer(task_expected_answer.expected_answer),
            )
            print(f"Task {task.id} output: {_task_out}")
