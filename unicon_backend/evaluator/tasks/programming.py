import abc
from enum import Enum
from typing import TYPE_CHECKING, Any, Generic

import requests
from pydantic import BaseModel, model_validator

from unicon_backend.evaluator.tasks.base import InputType, OutputType, Task
from unicon_backend.helpers.constants import RUNNER_URL
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
        pass_to_function = self.arguments + [
            f"{key}={value}" for key, value in self.keyword_arguments.items()
        ]
        return f"{self.function_name}({', '.join(map(str, pass_to_function))})"


class Request(BaseModel):
    files: list[File]
    environment: ProgrammingEnvironment
    entrypoint: str

    @model_validator(mode="after")
    def check_entrypoint_in_files(self):
        if self.entrypoint not in [file.file_name for file in self.files]:
            raise ValueError("entrypoint not in files")
        return self


class Testcase(BaseModel):
    id: int
    steps: list[Step]

    def run(self, answer: "Answer", environment: ProgrammingEnvironment):
        artifacts = answer.artifacts
        run_funcs = [step for step in self.steps if isinstance(step, PyRunFunctionStep)]
        file = template.render(prepend="", artifacts=artifacts, run_funcs=run_funcs)
        request = Request(
            files=[File(file_name="run.py", content=file)],
            environment=environment,
            entrypoint="run.py",
        )
        resp = requests.post(
            f"{RUNNER_URL}/submissions", data=request.model_dump_json()
        )
        print(resp.json())


class ProgrammingTask(Task[Any, Any]):
    question: str
    environment: ProgrammingEnvironment
    templates: list[File]
    testcases: list[Testcase]

    input: list[File]

    def run(self, answer: "Answer") -> bool:
        for testcase in self.testcases:
            testcase.run(answer, self.environment)

        # TODO: check output
        return True
