from enum import Enum
from typing import Any, NewType, Self
from uuid import UUID

from pydantic import BaseModel, model_validator

from unicon_backend.evaluator.tasks.programming.artifact import File


class RunnerType(str, Enum):
    PODMAN = "podman"
    SANDBOX = "sandbox"
    UNSAFE = "unsafe"


SubmissionId = NewType("SubmissionId", UUID)


class ProgrammingLanguage(str, Enum):
    PYTHON = "PYTHON"


class RunnerEnvironment(BaseModel):
    language: ProgrammingLanguage
    time_limit: int  # in seconds
    memory_limit: int  # in MB

    extra_options: dict[str, Any]


class RunnerResponse(BaseModel):
    submission_id: SubmissionId
    status: int
    stdout: str
    stderr: str


class RunnerPackage(BaseModel):
    entrypoint: str
    files: list[File]

    @model_validator(mode="after")
    def check_entrypoint_exists_in_files(self) -> Self:
        if not any(file.file_name == self.entrypoint for file in self.files):
            raise ValueError(f"Entrypoint {self.entrypoint} not found in RunnerPackage files")
        return self


class RunnerRequest(BaseModel):
    submission_id: SubmissionId
    package: RunnerPackage

    environment: RunnerEnvironment

    @classmethod
    def create(
        cls, entrypoint: str, files: list[File], environment: RunnerEnvironment
    ) -> "RunnerRequest":
        package = RunnerPackage(entrypoint=entrypoint, files=files)
        submission_id = SubmissionId(UUID())
        return RunnerRequest(submission_id=submission_id, package=package, environment=environment)
