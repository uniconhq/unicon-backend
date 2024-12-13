from functools import cached_property
from logging import getLogger
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from unicon_backend.evaluator.tasks.base import TaskEvalResult
from unicon_backend.evaluator.tasks.multiple_choice import MultipleChoiceTask, MultipleResponseTask
from unicon_backend.evaluator.tasks.programming.task import ProgrammingTask
from unicon_backend.evaluator.tasks.short_answer import ShortAnswerTask

logger = getLogger(__name__)


class ExpectedAnswer(BaseModel):
    task_id: int
    expected_answer: Any


class UserInput(BaseModel):
    task_id: int
    value: Any


Task = ProgrammingTask | MultipleChoiceTask | MultipleResponseTask | ShortAnswerTask


class Problem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str
    tasks: list[Annotated[Task, Field(discriminator="type")]]

    @cached_property
    def task_index(self) -> dict[int, Task]:
        return {task.id: task for task in self.tasks}

    def run_task(
        self, task_id: int, input: Any, expected_answer: ExpectedAnswer | None
    ) -> TaskEvalResult:
        # NOTE: It is safe to ignore type checking here because the type of task is determined by the "type" field
        # As long as the "type" field is set correctly, the type of task will be inferred correctly
        task = self.task_index[task_id]
        return task.run(
            task.validate_user_input(input),  # type: ignore
            None if expected_answer is None else task.validate_expected_answer(expected_answer),  # type: ignore
        )

    def run(
        self,
        user_inputs: list[UserInput],
        expected_answers: list[ExpectedAnswer],
        task_id: int | None = None,
    ) -> list[TaskEvalResult]:
        user_input_index: dict[int, UserInput] = {
            user_input.task_id: user_input for user_input in user_inputs
        }
        expected_answer_index: dict[int, ExpectedAnswer] = {
            task_answer.task_id: task_answer for task_answer in expected_answers
        }
        tasks_to_run = (
            self.tasks if task_id is None else [task for task in self.tasks if task.id == task_id]
        )

        result: list[TaskEvalResult] = []
        for task in tasks_to_run:
            task_user_input = user_input_index.get(task.id)
            if task_user_input is None:
                logger.warning(f"No user input found for task {task.id}")
                continue
            task_expected_answer = expected_answer_index.get(task.id)
            result.append(self.run_task(task.id, task_user_input.value, task_expected_answer))

        return result
