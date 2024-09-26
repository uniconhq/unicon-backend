import abc
import time
from enum import Enum
from http import HTTPStatus
from itertools import groupby
from typing import Any, Generic, TypeVar

import requests
from pydantic import BaseModel, RootModel, model_validator

from unicon_backend.evaluator.tasks.base import Task, TaskEvalResult, TaskEvalStatus
from unicon_backend.helpers.constants import RUNNER_URL
from unicon_backend.lib.common import CustomBaseModel


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


class RunnerRequest(BaseModel):
    files: list[File]
    environment: ProgrammingEnvironment
    entrypoint: str

    @model_validator(mode="after")
    def check_entrypoint_in_files(self):
        if self.entrypoint not in [file.file_name for file in self.files]:
            raise ValueError("entrypoint not in files")
        return self


class RunnerResponse(BaseModel):
    # Reference: https://github.com/uniconhq/unicon-runner/blob/main/unicon_runner/executor/run.py#L69-L73
    status: int
    stdout: str
    stderr: str


def run_program(
    files: list[File],
    environment: ProgrammingEnvironment,
    entrypoint: str,
    wait: bool = False,
) -> RunnerResponse | None:
    if not RUNNER_URL:
        print("WARN: No programming task runner set!")
        return None

    runner_resp = requests.post(
        f"{RUNNER_URL}/run",
        data=RunnerRequest(
            files=files,
            environment=environment,
            entrypoint=entrypoint,
        ).model_dump_json(),
    )

    submission_id = runner_resp.json()["submission_id"]
    if not wait:
        return submission_id

    while True:
        resp = requests.get(f"{RUNNER_URL}/submissions/{submission_id}")
        if resp.status_code == HTTPStatus.OK:
            break
        time.sleep(1)

    return RunnerResponse.model_validate(resp.json())


class StepType(str, Enum):
    PY_RUN_FUNCTION = "PY_RUN_FUNCTION_STEP"
    STDOUT_COMPARE = "STDOUT_COMPARE_STEP"


StepInputType = TypeVar("StepInputType")
StepExpectedAnswer = TypeVar("StepExpectedAnswer")
StepOutputType = TypeVar("StepOutputType")


class Step(
    CustomBaseModel,
    abc.ABC,
    Generic[StepInputType, StepExpectedAnswer, StepOutputType],
    polymorphic=True,
):
    id: int
    type: StepType

    @abc.abstractmethod
    def run(
        self,
        user_input: StepInputType,
        expected_answer: StepExpectedAnswer,
        environment: ProgrammingEnvironment,
    ) -> StepOutputType:
        pass


class PyRunFunctionStep(Step[list[File], None, Any]):
    file_name: str
    function_name: str
    arguments: list[int | str]
    keyword_arguments: dict[str, str]

    def run(
        self, user_input: list[File], _: None, environment: ProgrammingEnvironment
    ) -> Any:
        def stringify_arg(arg: int | str) -> str:
            return str(arg) if isinstance(arg, int) else f'"{arg}"'

        if not any(f.file_name == self.file_name for f in user_input):
            raise ValueError(f"File {self.file_name} not found in input files")

        func_args_kwargs = [stringify_arg(arg) for arg in self.arguments] + [
            f"{k}={stringify_arg(v)}" for k, v in self.keyword_arguments.items()
        ]
        func_invocation = f"{self.function_name}({', '.join(func_args_kwargs)})"
        assembled_code = f"from {self.file_name} import {self.function_name}\n\nprint({func_invocation})"

        # TODO: Standardize runner response
        # For now, just return the stdout
        return run_program(
            user_input + [File(file_name="__run.py", content=assembled_code)],
            environment,
            "__run.py",
        )


class StdoutCompareStep(Step[RunnerResponse | None, str, bool]):
    def run(
        self,
        input: RunnerResponse | None,
        expected_answer: str,
        _: ProgrammingEnvironment,
    ) -> bool:
        if input is None:
            print("WARN: no input to compare")
            return False
        return input.stdout == expected_answer


class ProgrammingTaskExpectedAnswer(BaseModel):
    testcase_id: int
    step_id: int
    expected_answer: Any


class Testcase(BaseModel):
    id: int
    steps: list[Step]

    def run(
        self,
        user_input: list[File],
        expected_answer: list[ProgrammingTaskExpectedAnswer],
        environment: ProgrammingEnvironment,
    ):
        expected_answer_by_step = {
            step_expected_answer.step_id: step_expected_answer.expected_answer
            for step_expected_answer in expected_answer
        }

        # TEMP: Assume that steps are a linear sequence and run them in order
        step_idx: int = 0
        prev_step_output: Any = user_input
        while step_idx < len(self.steps):
            step = self.steps[step_idx]

            step_expected_answer = expected_answer_by_step.get(step.id)
            step_output = step.run(prev_step_output, step_expected_answer, environment)

            prev_step_output = step_output
            step_idx += 1

        return prev_step_output


class ProgrammingTask(Task[list[File], bool, list[ProgrammingTaskExpectedAnswer]]):
    question: str
    environment: ProgrammingEnvironment
    templates: list[File]
    testcases: list[Testcase]

    def run(
        self,
        user_input: list[File],
        expected_answer: list[ProgrammingTaskExpectedAnswer],
    ) -> TaskEvalResult[bool]:
        expected_answer_by_testcase = {
            testcase_id: list(group)
            for testcase_id, group in groupby(expected_answer, lambda x: x.testcase_id)
        }

        for testcase in self.testcases:
            testcase_expected_answer = expected_answer_by_testcase.get(testcase.id)
            if not testcase_expected_answer:
                print(f"WARN: Testcase {testcase.id} has no expected answer")
                continue
            testcase.run(user_input, testcase_expected_answer, self.environment)

        # TODO: check output and handle pending testcases
        return TaskEvalResult(status=TaskEvalStatus.SUCCESS, result=False)

    def validate_user_input(self, user_input: Any) -> list[File]:
        return RootModel[list[File]].model_validate(user_input).root

    def validate_expected_answer(
        self, expected_answer: Any
    ) -> list[ProgrammingTaskExpectedAnswer]:
        return (
            RootModel[list[ProgrammingTaskExpectedAnswer]]
            .model_validate(expected_answer)
            .root
        )
