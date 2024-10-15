from enum import Enum
from logging import getLogger
from typing import Any, NewType
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, RootModel

from unicon_backend.evaluator.tasks import Task, TaskEvalResult, TaskEvalStatus
from unicon_backend.lib.graph import Graph, GraphNode
from unicon_backend.workers import task_publisher

logger = getLogger(__name__)


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


class Step(GraphNode):
    model_config = ConfigDict(extra="allow")

    type: str


class Testcase(Graph[Step]):
    id: int


class ExecutorType(str, Enum):
    PODMAN = "podman"
    SANDBOX = "sandbox"
    UNSAFE = "unsafe"


class ProgrammingTaskExpectedAnswer(BaseModel):
    testcase_id: int
    step_id: int
    expected_answer: Any


SubmissionId = NewType("SubmissionId", UUID)


class ProgrammingTaskRequest(BaseModel):
    submission_id: SubmissionId
    environment: ProgrammingEnvironment
    templates: list[File]
    testcases: list[Testcase]
    user_input: list[File]
    expected_answer: list[ProgrammingTaskExpectedAnswer]
    executor_type: ExecutorType


class ProgrammingTask(Task[list[File], SubmissionId, list[ProgrammingTaskExpectedAnswer]]):
    question: str
    environment: ProgrammingEnvironment
    templates: list[File]
    testcases: list[Testcase]
    executor_type: ExecutorType = ExecutorType.PODMAN

    def run(
        self,
        user_input: list[File],
        expected_answer: list[ProgrammingTaskExpectedAnswer],
    ) -> TaskEvalResult[SubmissionId]:
        submission_id = SubmissionId(uuid4())

        for testcase in self.testcases:
            testcase.topological_sort()

        request = ProgrammingTaskRequest(
            submission_id=submission_id,
            environment=self.environment,
            templates=self.templates,
            testcases=self.testcases,
            user_input=user_input,
            expected_answer=expected_answer,
            executor_type=self.executor_type,
        )

        task_publisher.publish(request.model_dump_json(serialize_as_any=True))

        return TaskEvalResult(task_id=self.id, status=TaskEvalStatus.PENDING, result=submission_id)

    def validate_user_input(self, user_input: Any) -> list[File]:
        return RootModel[list[File]].model_validate(user_input).root

    def validate_expected_answer(self, expected_answer: Any) -> list[ProgrammingTaskExpectedAnswer]:
        return RootModel[list[ProgrammingTaskExpectedAnswer]].model_validate(expected_answer).root
