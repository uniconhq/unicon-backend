import abc
from enum import Enum
from typing import Generic, TypeVar, Any

from pydantic import BaseModel

from unicon_backend.lib.common import CustomBaseModel

TaskInputType = TypeVar("TaskInputType")
TaskResultType = TypeVar("TaskResultType")
TaskAnswerType = TypeVar("TaskAnswerType")


class TaskEvaluationStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PENDING = "PENDING"
    SKIPPED = "SKIPPED"


class TaskEvaluationResult(BaseModel, Generic[TaskResultType]):
    status: TaskEvaluationStatus
    result: TaskResultType | None


class TaskType(str, Enum):
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE_TASK"
    MULTIPLE_RESPONSE = "MULTIPLE_RESPONSE_TASK"
    SHORT_ANSWER = "SHORT_ANSWER_TASK"
    PROGRAMMING = "PROGRAMMING_TASK"


class Task(
    CustomBaseModel,
    abc.ABC,
    Generic[TaskInputType, TaskResultType, TaskAnswerType],
    polymorphic=True,
):
    id: int
    type: str
    autograde: bool = True

    input: TaskInputType

    @abc.abstractmethod
    def run(self, expected: TaskAnswerType) -> TaskEvaluationResult[TaskResultType]:
        pass

    @abc.abstractmethod
    def validate_answer(self, answer: Any) -> TaskAnswerType:
        pass
