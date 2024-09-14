import abc
from enum import Enum
from typing import Generic, TypeVar, Any

from unicon_backend.lib.common import CustomBaseModel


class TaskType(str, Enum):
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE_TASK"
    MULTIPLE_RESPONSE = "MULTIPLE_RESPONSE_TASK"
    SHORT_ANSWER = "SHORT_ANSWER_TASK"
    PROGRAMMING = "PROGRAMMING_TASK"


TaskInputType = TypeVar("InputType")
TaskOutputType = TypeVar("OutputType")
TaskAnswerType = TypeVar("AnswerType")


class Task(
    CustomBaseModel,
    abc.ABC,
    Generic[TaskInputType, TaskOutputType, TaskAnswerType],
    polymorphic=True,
):
    id: int
    type: str
    autograde: bool = True

    input: TaskInputType

    @abc.abstractmethod
    def run(self, expected: TaskAnswerType) -> TaskOutputType:
        pass

    @abc.abstractmethod
    def validate_answer(self, answer: Any) -> TaskAnswerType:
        pass
