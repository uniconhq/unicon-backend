from enum import Enum
from typing import Any, NewType, Self
from uuid import uuid4

from pydantic import BaseModel, model_validator

from unicon_backend.evaluator.tasks.programming.artifact import File

SubmissionId = NewType("SubmissionId", str)


class ProgrammingLanguage(str, Enum):
    PYTHON = "PYTHON"


class RunnerEnvironment(BaseModel):
    language: ProgrammingLanguage
    time_limit: int  # in seconds
    memory_limit: int  # in MB

    extra_options: dict[str, Any] | None = None


class TaskEvalStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PENDING = "PENDING"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class Status(str, Enum):
    OK = "OK"
    MLE = "MLE"
    TLE = "TLE"
    RTE = "RTE"
    WA = "WA"


class Result(BaseModel):
    id: int
    status: Status
    stdout: str
    stderr: str


class RunnerResponse(BaseModel):
    submission_id: SubmissionId
    status: TaskEvalStatus
    result: list[Result]


class RunnerPackage(BaseModel):
    id: int  # used for testcase_id
    entrypoint: str
    files: list[File]

    @model_validator(mode="after")
    def check_entrypoint_exists_in_files(self) -> Self:
        if not any(file.file_name == self.entrypoint for file in self.files):
            raise ValueError(f"Entrypoint {self.entrypoint} not found in RunnerPackage files")
        return self


class RunnerRequest(BaseModel):
    submission_id: SubmissionId
    programs: list[RunnerPackage]
    environment: RunnerEnvironment

    @classmethod
    def create(
        cls, programs: list[RunnerPackage], environment: RunnerEnvironment
    ) -> "RunnerRequest":
        submission_id = SubmissionId(str(uuid4()))
        return RunnerRequest(
            submission_id=submission_id, programs=programs, environment=environment
        )
