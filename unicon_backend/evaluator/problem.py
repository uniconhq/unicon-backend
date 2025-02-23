from datetime import datetime
from functools import cached_property
from logging import getLogger
from typing import Annotated, Any

from pydantic import BaseModel, Field
from sqlmodel._compat import SQLModelConfig

from unicon_backend.evaluator.tasks.base import TaskEvalResult
from unicon_backend.evaluator.tasks.multiple_choice import MultipleChoiceTask, MultipleResponseTask
from unicon_backend.evaluator.tasks.programming.base import ProgrammingTask
from unicon_backend.evaluator.tasks.short_answer import ShortAnswerTask
from unicon_backend.lib.common import CustomSQLModel

logger = getLogger(__name__)


class UserInput(BaseModel):
    task_id: int
    value: Any


Task = ProgrammingTask | MultipleChoiceTask | MultipleResponseTask | ShortAnswerTask


class Problem(CustomSQLModel):
    model_config = SQLModelConfig(from_attributes=True)

    name: str
    restricted: bool
    published: bool = Field(default=False)
    description: str
    tasks: list[Annotated[Task, Field(discriminator="type")]]
    started_at: datetime
    ended_at: datetime
    closed_at: datetime | None = Field(default=None)

    @cached_property
    def task_index(self) -> dict[int, Task]:
        return {task.id: task for task in self.tasks}

    def run_task(self, task_id: int, input: Any) -> TaskEvalResult:
        # NOTE: It is safe to ignore type checking here because the type of task is determined by the "type" field
        # As long as the "type" field is set correctly, the type of task will be inferred correctly
        task = self.task_index[task_id]
        return task.run(
            task.validate_user_input(input),  # type: ignore
        )

    def run(
        self,
        user_inputs: list[UserInput],
        task_id: int | None = None,
    ) -> list[TaskEvalResult]:
        user_input_index: dict[int, UserInput] = {
            user_input.task_id: user_input for user_input in user_inputs
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
            result.append(self.run_task(task.id, task_user_input.value))

        return result

    def redact_private_fields(self):
        """This is a destructive in-place action. Do not attempt to assemble code after redacting private fields."""
        for task in self.tasks:
            task.redact_private_fields()
