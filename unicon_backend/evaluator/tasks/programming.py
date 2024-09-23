import abc
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, model_validator

from unicon_backend.evaluator.tasks.base import (
    Task,
    TaskEvaluationResult,
    TaskEvaluationStatus,
)
from unicon_backend.helpers.constants import RUNNER_URL
from unicon_backend.lib.common import CustomBaseModel
from unicon_backend.templates import template

import pika


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
    CHECK_OUTPUT = "CHECK_OUTPUT_STEP"


SteptInputType = TypeVar("SteptInputType")
SteptOutputType = TypeVar("SteptOutputType")


class Step(
    CustomBaseModel, abc.ABC, Generic[SteptInputType, SteptOutputType], polymorphic=True
):
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


class OutputFile(BaseModel):
    value: str


class CheckOutputStep(Step[Any, Any]):
    value: File | OutputFile


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

    def run(self, input_files: list[File], environment: ProgrammingEnvironment):
        run_funcs = [step for step in self.steps if isinstance(step, PyRunFunctionStep)]
        file = template.render(prepend="", artifacts=input_files, run_funcs=run_funcs)

        print(f"Testcase File (run.py):\n {file}")

        self._run_code(file, environment)

    def check(self, user_result, environment: ProgrammingEnvironment):
        """This part currently not used: (_run_code) doesnt return the result immediately anymore"""
        run_funcs = [step for step in self.steps if isinstance(step, PyRunFunctionStep)]

        check_steps = [step for step in self.steps if isinstance(step, CheckOutputStep)]
        for check_step in check_steps:
            if isinstance(check_step.value, OutputFile):
                if check_step.value.value != user_result["stdout"]:
                    user_result["status"] = "WA"
                    break
            if isinstance(check_step.value, File):
                sample_file = template.render(
                    prepend="", artifacts=[check_step.value], run_funcs=run_funcs
                )
                correct_output = self._run_code(sample_file, environment)
                if correct_output["stdout"] != user_result["stdout"]:
                    user_result["status"] = "WA"
                    break

        return user_result

    def _run_code(self, file: str, environment: ProgrammingEnvironment):
        request = Request(
            files=[File(file_name="run.py", content=file)],
            environment=environment,
            entrypoint="run.py",
        )

        if not RUNNER_URL:
            print("WARN: No programming task runner set!")
            return

        # Send a request to the runner via MQ
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host="localhost")
        )
        send_channel = connection.channel()
        send_channel.queue_declare(queue="task_runner", durable=True)

        message = request.model_dump_json()
        send_channel.basic_publish(exchange="", routing_key="task_runner", body=message)
        connection.close()


# TODO: Implement different types of answer types
# For example, `stdout` / `OutputFile` (for file comparison) / `File` (for running code and comparing output)
class ProgrammingTask(Task[list[File], bool, list[File]]):
    question: str
    environment: ProgrammingEnvironment
    templates: list[File]
    testcases: list[Testcase]

    input: list[File]

    def run(self, _expected: list[File]) -> TaskEvaluationResult[bool]:
        for testcase in self.testcases:
            testcase.run(_expected, self.environment)

        # TODO: check output and handle pending testcases
        return TaskEvaluationResult(status=TaskEvaluationStatus.SUCCESS, result=True)

    def validate_answer(self, answer: Any) -> list[File]:
        if not isinstance(answer, list):
            raise ValueError("Answer must be a list of files")

        return [File.model_validate(file) for file in answer]
