import abc
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from unicon_backend.models.contest import TaskEvalStatus, TaskType

TaskUserInput = TypeVar("TaskUserInput")
TaskExpectedAnswer = TypeVar("TaskExpectedAnswer")
TaskResult = TypeVar("TaskResult")


class TaskEvalResult(BaseModel, Generic[TaskResult]):
    task_id: int
    status: TaskEvalStatus
    result: TaskResult | None
    error: str | None = None


class Task(BaseModel, abc.ABC, Generic[TaskUserInput, TaskResult, TaskExpectedAnswer]):
    id: int
    type: TaskType
    autograde: bool = True

    @abc.abstractmethod
    def run(
        self, user_input: TaskUserInput, expected_answer: TaskExpectedAnswer
    ) -> TaskEvalResult[TaskResult]:
        pass

    @abc.abstractmethod
    def validate_user_input(self, user_input: Any) -> TaskUserInput:
        pass

    @abc.abstractmethod
    def validate_expected_answer(self, expected_answer: Any) -> TaskExpectedAnswer:
        pass
