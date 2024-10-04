import abc
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from unicon_backend.lib.common import CustomBaseModel

TaskUserInput = TypeVar("TaskUserInput")
TaskExpectedAnswer = TypeVar("TaskExpectedAnswer")
TaskResult = TypeVar("TaskResult")


class TaskType(str, Enum):
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE_TASK"
    MULTIPLE_RESPONSE = "MULTIPLE_RESPONSE_TASK"
    SHORT_ANSWER = "SHORT_ANSWER_TASK"
    PROGRAMMING = "PROGRAMMING_TASK"


class TaskEvalStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PENDING = "PENDING"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class TaskEvalResult(BaseModel, Generic[TaskResult]):
    task_id: int
    status: TaskEvalStatus
    result: TaskResult | None
    error: str | None = None


class Task(
    CustomBaseModel,
    abc.ABC,
    Generic[TaskUserInput, TaskResult, TaskExpectedAnswer],
    polymorphic=True,
):
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
