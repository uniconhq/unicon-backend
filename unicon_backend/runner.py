from enum import Enum
from typing import NewType, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, model_validator

from unicon_backend.evaluator.tasks.programming.artifact import File

JobId = NewType("JobId", UUID)


class Language(str, Enum):
    PYTHON = "PYTHON"


class ComputeContext(BaseModel):
    language: Language
    time_limit_secs: int
    memory_limit_mb: int

    extra_options: dict[str, str] | None = None


class Status(str, Enum):
    OK = "OK"
    MLE = "MLE"
    TLE = "TLE"
    RTE = "RTE"
    WA = "WA"


class ProgramResult(BaseModel):
    status: Status
    stdout: str
    stderr: str

    # Tracking fields
    id: int  # Corresponds to the testcase id of the problem


class JobResult(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    success: bool
    error: str | None
    results: list[ProgramResult]

    # Tracking fields
    id: JobId


class RunnerProgram(BaseModel):
    entrypoint: str
    files: list[File]

    # Tracking fields
    id: int  # Corresponds to the testcase id of the problem

    @model_validator(mode="after")
    def check_entrypoint_exists_in_files(self) -> Self:
        if not any(file.name == self.entrypoint for file in self.files):
            raise ValueError(f"Entrypoint {self.entrypoint} not found in program files")
        return self


class RunnerJob(BaseModel):
    programs: list[RunnerProgram]
    context: ComputeContext

    # Tracking fields
    id: JobId

    @classmethod
    def create(cls, programs: list[RunnerProgram], environment: ComputeContext) -> "RunnerJob":
        return RunnerJob(id=JobId(uuid4()), programs=programs, context=environment)
