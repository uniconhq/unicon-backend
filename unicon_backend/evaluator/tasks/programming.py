import abc
import logging
from enum import Enum
from logging import getLogger
from typing import Any, Generic, Literal, TypeVar
from uuid import uuid4

import pika  # type: ignore
from pydantic import BaseModel, RootModel

from unicon_backend.constants import RABBITMQ_URL
from unicon_backend.evaluator.tasks.base import Task, TaskEvalResult, TaskEvalStatus
from unicon_backend.lib.common import CustomBaseModel

logger = getLogger(__name__)

# TEMP: suppress pika logging
logging.getLogger("pika").setLevel(logging.WARNING)


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


class RunnerResponse(BaseModel):
    # Reference: https://github.com/uniconhq/unicon-runner/blob/main/unicon_runner/executor/run.py#L69-L73
    submission_id: str
    status: int
    stdout: str
    stderr: str


class StepType(str, Enum):
    PY_RUN_FUNCTION = "PY_RUN_FUNCTION_STEP"
    EXTRACT_PROGRAM_OUTPUT = "EXTRACT_PROGRAM_OUTPUT_STEP"
    STRING_MATCH = "STRING_MATCH_STEP"


StepInputType = TypeVar("StepInputType")
StepExpectedAnswer = TypeVar("StepExpectedAnswer")
StepOutputType = TypeVar("StepOutputType")

type Unused = None


class Step(
    CustomBaseModel,
    abc.ABC,
    Generic[StepInputType, StepExpectedAnswer, StepOutputType],
    polymorphic=True,
):
    id: int
    type: StepType


class PyRunFunctionStep(Step[list[File], Unused, RunnerResponse]):
    file_name: str
    function_name: str
    arguments: list[int | str]
    keyword_arguments: dict[str, str]


class ExtractProgramOutputStep(Step[RunnerResponse, Unused, str]):
    key: Literal["stdout", "stderr", "status"]


class StringMatchStep(Step[str, str, bool]): ...


class ProgrammingTaskExpectedAnswer(BaseModel):
    testcase_id: int
    step_id: int
    expected_answer: Any


class Testcase(BaseModel):
    id: int
    steps: list[Step]


class ProgrammingTaskRequest(BaseModel):
    submission_id: str
    environment: ProgrammingEnvironment
    templates: list[File]
    testcases: list[Testcase]
    user_input: list[File]
    expected_answer: list[ProgrammingTaskExpectedAnswer]
    executor_type: Literal["podman", "unsafe"] = "podman"


class ProgrammingTask(Task[list[File], str, list[ProgrammingTaskExpectedAnswer]]):
    question: str
    environment: ProgrammingEnvironment
    templates: list[File]
    testcases: list[Testcase]
    executor_type: Literal["podman", "unsafe"] = "podman"

    def run(
        self,
        user_input: list[File],
        expected_answer: list[ProgrammingTaskExpectedAnswer],
    ) -> TaskEvalResult[str]:
        submission_id = str(uuid4())
        request = ProgrammingTaskRequest(
            submission_id=submission_id,
            environment=self.environment,
            templates=self.templates,
            testcases=self.testcases,
            user_input=user_input,
            expected_answer=expected_answer,
        )
        self.send_to_runner(request)

        # TODO: check output and handle pending testcases
        # TODO: maybe move submission id else where
        return TaskEvalResult(status=TaskEvalStatus.PENDING, result=submission_id)

    def validate_user_input(self, user_input: Any) -> list[File]:
        return RootModel[list[File]].model_validate(user_input).root

    def validate_expected_answer(self, expected_answer: Any) -> list[ProgrammingTaskExpectedAnswer]:
        return RootModel[list[ProgrammingTaskExpectedAnswer]].model_validate(expected_answer).root

    def send_to_runner(self, request: ProgrammingTaskRequest) -> str:
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        send_channel = connection.channel()
        send_channel.queue_declare(queue="task_runner", durable=True)

        message = request.model_dump_json(serialize_as_any=True)
        send_channel.basic_publish(exchange="", routing_key="task_runner", body=message)
        connection.close()

        return ""
