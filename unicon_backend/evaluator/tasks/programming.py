import abc
from enum import Enum
import os
from typing import Any, TYPE_CHECKING, Generic
from uuid import uuid4

from pydantic import BaseModel

from unicon_backend.evaluator.tasks.base import InputType, OutputType, Task
from unicon_backend.lib.common import CustomBaseModel
from unicon_backend.templates import template

if TYPE_CHECKING:
    from unicon_backend.evaluator.answer import Answer

OUTPUT_FOLDER = "output"


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

    def get_code(self):
        pass_to_function = self.arguments + \
            [f"{key}={value}" for key, value in self.keyword_arguments.items()]
        return f"{self.function_name}({', '.join(map(str, pass_to_function))})"


class Testcase(BaseModel):
    id: int
    steps: list[Step]

    def run(self, prefix: str, answer: "Answer"):
        folder_path = os.path.join(OUTPUT_FOLDER, prefix, str(self.id))
        os.mkdir(folder_path)
        artifacts = answer.artifacts
        run_funcs = [step for step in self.steps if isinstance(
            step, PyRunFunctionStep)]
        file = template.render(
            prepend="", artifacts=artifacts, run_funcs=run_funcs)
        with open(os.path.join(folder_path, "run.py"), "w") as f:
            f.write(file)


class ProgrammingTask(Task[Any, Any]):
    question: str
    environment: ProgrammingEnvironment
    templates: list[File]
    testcases: list[Testcase]

    input: list[File]

    def run(self, answer: "Answer") -> bool:
        prefix = str(uuid4())
        if OUTPUT_FOLDER not in os.listdir():
            os.mkdir(OUTPUT_FOLDER)
        os.mkdir(os.path.join(OUTPUT_FOLDER, prefix))
        for testcase in self.testcases:
            testcase.run(prefix, answer)
