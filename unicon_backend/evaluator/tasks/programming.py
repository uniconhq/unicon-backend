from enum import Enum
from typing import Any

from pydantic import BaseModel

from unicon_backend.evaluator.tasks.base import Task


class ProgrammingLanguage(str, Enum):
    PYTHON = "PYTHON"


class ProgrammingEnvironment(BaseModel):
    language: ProgrammingLanguage
    options: dict[str, str]
    time_limit: int  # in seconds
    memory_limit: int  # in MB


class File(BaseModel):
    file_name: str
    content: str


class StepType(str, Enum):
    PY_RUN_FUNCTION = "PY_RUN_FUNCTION_STEP"


class Step(CustomBaseModel, abc.ABC, Generic[InputType, OutputType], polymorphic=True):
    id: int
    type: StepType


class PyRunFunctionStep(Step[Any, Any]):
    function_name: str
    arguments: list[str | int]
    keyword_arguments: dict[str, str]


class Testcase(BaseModel):
    id: int
    steps: list[Step]


class ProgrammingTask(Task[Any, Any]):
    question: str
    environment: ProgrammingEnvironment
    templates: list[File]
    testcases: list[Testcase]

    input: list[File]

    def run(self, expected: Any) -> Any:
        raise NotImplementedError()
