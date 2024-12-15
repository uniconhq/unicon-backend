import abc
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from unicon_backend.evaluator.tasks.programming.runner import TaskEvalStatus

TaskUserInput = TypeVar("TaskUserInput")
TaskResult = TypeVar("TaskResult")


class TaskType(str, Enum):
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE_TASK"
    MULTIPLE_RESPONSE = "MULTIPLE_RESPONSE_TASK"
    SHORT_ANSWER = "SHORT_ANSWER_TASK"
    PROGRAMMING = "PROGRAMMING_TASK"


class TaskEvalResult(BaseModel, Generic[TaskResult]):
    task_id: int
    status: TaskEvalStatus
    result: TaskResult | None
    error: str | None = None


class Task(BaseModel, abc.ABC, Generic[TaskUserInput, TaskResult]):
    id: int
    type: TaskType
    autograde: bool = True

    @abc.abstractmethod
    def run(self, user_input: TaskUserInput) -> TaskEvalResult[TaskResult]:
        pass

    @abc.abstractmethod
    def validate_user_input(self, user_input: Any) -> TaskUserInput:
        pass
