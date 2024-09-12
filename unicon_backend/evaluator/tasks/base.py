import abc
from enum import Enum
from typing import Generic, TypeVar

from unicon_backend.lib.common import CustomBaseModel


class TaskType(str, Enum):
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE_TASK"
    MULTIPLE_RESPONSE = "MULTIPLE_RESPONSE_TASK"
    SHORT_ANSWER = "SHORT_ANSWER_TASK"
    PROGRAMMING = "PROGRAMMING_TASK"


InputType = TypeVar("InputType")
OutputType = TypeVar("OutputType")


class Task(CustomBaseModel, abc.ABC, Generic[InputType, OutputType], polymorphic=True):
    id: int
    type: str
    autograde: bool = True

    input: InputType

    @abc.abstractmethod
    def run(self, expected: InputType) -> OutputType:
        pass
