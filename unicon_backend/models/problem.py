from datetime import datetime
from typing import TYPE_CHECKING, Any, Self

import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg
import sqlalchemy.orm as sa_orm
from pydantic import model_validator
from sqlmodel import Field, Relationship

from unicon_backend.evaluator.problem import Problem
from unicon_backend.evaluator.tasks import task_classes
from unicon_backend.evaluator.tasks.base import TaskEvalResult, TaskEvalStatus, TaskType
from unicon_backend.evaluator.tasks.programming.base import TestcaseResult
from unicon_backend.lib.common import CustomSQLModel

if TYPE_CHECKING:
    from unicon_backend.evaluator.tasks.base import Task
    from unicon_backend.models.organisation import Project


# Factory function for creating a timestamp column (with timezone)
_timestamp_column = lambda nullable, default: sa.Column(
    pg.TIMESTAMP(timezone=True),
    nullable=nullable,
    server_default=sa.func.now() if default else None,
)


class ProblemBase(CustomSQLModel):
    id: int
    name: str
    description: str
    project_id: int


class ProblemORM(CustomSQLModel, table=True):
    __tablename__ = "problem"

    id: int = Field(primary_key=True)
    name: str
    description: str

    project_id: int = Field(foreign_key="project.id")

    tasks: sa_orm.Mapped[list["TaskORM"]] = Relationship(back_populates="problem")
    project: sa_orm.Mapped["Project"] = Relationship(back_populates="problems")
    submissions: sa_orm.Mapped[list["SubmissionORM"]] = Relationship(back_populates="problem")

    @classmethod
    def from_problem(cls, problem: "Problem") -> "ProblemORM":
        tasks_orm: list[TaskORM] = [TaskORM.from_task(task) for task in problem.tasks]
        return cls(name=problem.name, description=problem.description, tasks=tasks_orm)

    def to_problem(self) -> "Problem":
        def _serialize_task(t: TaskORM):
            return {"id": t.id, "type": t.type, "autograde": t.autograde, **t.other_fields}

        return Problem.model_validate(
            {
                "name": self.name,
                "description": self.description,
                "tasks": [_serialize_task(task_orm) for task_orm in self.tasks],
            }
        )


class TaskORM(CustomSQLModel, table=True):
    __tablename__ = "task"

    id: int = Field(primary_key=True)

    type: TaskType = Field(sa_column=sa.Column(pg.ENUM(TaskType), nullable=False))
    autograde: bool
    other_fields: dict = Field(default_factory=dict, sa_column=sa.Column(pg.JSONB))

    problem_id: int = Field(foreign_key="problem.id", primary_key=True)

    problem: sa_orm.Mapped[ProblemORM] = Relationship(back_populates="tasks")
    task_attempts: sa_orm.Mapped[list["TaskAttemptORM"]] = Relationship(back_populates="task")

    @classmethod
    def from_task(cls, task: "Task") -> "TaskORM":
        def _convert_task_to_orm(id: int, type: TaskType, autograde: bool, **other_fields):
            return TaskORM(id=id, type=type, autograde=autograde, other_fields=other_fields)

        return _convert_task_to_orm(**task.model_dump(serialize_as_any=True))

    def to_task(self) -> "Task":
        return task_classes[self.type].model_validate(
            {
                "id": self.id,
                "type": self.type,
                "autograde": self.autograde,
                **self.other_fields,
            }
        )


class SubmissionAttemptLink(CustomSQLModel, table=True):
    __tablename__ = "submission_attempt"

    submission_id: int = Field(foreign_key="submission.id", primary_key=True)
    task_attempt_id: int = Field(foreign_key="task_attempt.id", primary_key=True)


class SubmissionBase(CustomSQLModel):
    __tablename__ = "submission"

    id: int = Field(primary_key=True)
    problem_id: int = Field(foreign_key="problem.id")
    user_id: int = Field(foreign_key="user.id")

    submitted_at: datetime | None = Field(sa_column=_timestamp_column(nullable=False, default=True))


class SubmissionORM(SubmissionBase, table=True):
    task_attempts: sa_orm.Mapped[list["TaskAttemptORM"]] = Relationship(
        link_model=SubmissionAttemptLink, back_populates="submissions"
    )
    problem: sa_orm.Mapped[ProblemORM] = Relationship(back_populates="submissions")


class SubmissionPublic(SubmissionBase):
    task_attempts: list["TaskAttemptPublic"]


class TaskAttemptBase(CustomSQLModel):
    id: int
    user_id: int
    task_id: int
    task_type: TaskType
    other_fields: dict


class TaskAttemptPublic(TaskAttemptBase):
    task_results: list["TaskResult"]
    task: "TaskORM"


class TaskAttemptResult(TaskAttemptBase):
    task_results: list["TaskResult"]


class TaskAttemptORM(CustomSQLModel, table=True):
    __tablename__ = "task_attempt"
    __table_args__ = (
        sa.ForeignKeyConstraint(["task_id", "problem_id"], ["task.id", "task.problem_id"]),
    )

    id: int = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id", nullable=False)
    task_id: int
    problem_id: int

    submitted_at: datetime = Field(sa_column=_timestamp_column(nullable=False, default=True))
    task_type: TaskType = Field(sa_column=sa.Column(pg.ENUM(TaskType), nullable=False))

    # TODO: figure out polymorphism to stop abusing JSONB
    other_fields: dict = Field(default_factory=dict, sa_column=sa.Column(pg.JSONB))

    submissions: sa_orm.Mapped[list[SubmissionORM]] = Relationship(
        back_populates="task_attempts", link_model=SubmissionAttemptLink
    )
    task: sa_orm.Mapped[TaskORM] = Relationship(back_populates="task_attempts")
    task_results: sa_orm.Mapped[list["TaskResultORM"]] = Relationship(back_populates="task_attempt")


class TaskResultBase(CustomSQLModel):
    __tablename__ = "task_result"

    id: int = Field(primary_key=True)

    task_attempt_id: int = Field(foreign_key="task_attempt.id")
    task_type: TaskType = Field(sa_column=sa.Column(pg.ENUM(TaskType), nullable=False))

    started_at: datetime = Field(sa_column=_timestamp_column(nullable=False, default=True))
    completed_at: datetime | None = Field(sa_column=_timestamp_column(nullable=True, default=False))

    # NOTE: Unique identifier for a worker job that evaluates the task
    job_id: str | None = Field(nullable=True, unique=True)

    status: TaskEvalStatus = Field(sa_column=sa.Column(pg.ENUM(TaskEvalStatus), nullable=False))
    # TODO: Handle non-JSON result types for non-programming tasks
    result: Any = Field(default_factory=dict, sa_column=sa.Column(pg.JSONB))
    error: str | None = Field(nullable=True)


class TaskResultPublic(TaskResultBase):
    pass


class TaskResultORM(TaskResultBase, table=True):
    __tablename__ = "task_result"

    task_attempt: sa_orm.Mapped[TaskAttemptORM] = Relationship(back_populates="task_results")

    @classmethod
    def from_task_eval_result(
        cls, eval_result: "TaskEvalResult", attempt_id: int, task_type: TaskType
    ) -> "TaskResultORM":
        is_pending = eval_result.status == TaskEvalStatus.PENDING
        started_at = sa.func.now()
        completed_at = None if is_pending else sa.func.now()
        result = (
            eval_result.result.model_dump(mode="json")
            if not is_pending and eval_result.result
            else None
        )
        # NOTE: We assume that the job_id is always the result of a pending evaluation
        job_id = eval_result.result if is_pending else None

        return cls(
            task_attempt_id=attempt_id,
            task_type=task_type,
            started_at=started_at,
            completed_at=completed_at,
            status=eval_result.status,
            error=eval_result.error,
            result=result,
            job_id=job_id,
        )


"""
Below classes are for parsing/validating task results with pydantic
"""


class MultipleChoiceTaskResult(TaskResultPublic):
    result: bool

    @model_validator(mode="after")
    def validate_task_type(self) -> Self:
        if not self.task_type == TaskType.MULTIPLE_CHOICE:
            raise ValueError(f"Task type must be {TaskType.MULTIPLE_CHOICE}")
        return self


class MultipleResponseTaskResultType(CustomSQLModel):
    correct_choices: list[int]
    incorrect_choices: list[int]
    num_choices: int


class MultipleResponseTaskResult(TaskResultPublic):
    result: MultipleResponseTaskResultType | None

    @model_validator(mode="after")
    def validate_task_type(self) -> Self:
        if not self.task_type == TaskType.MULTIPLE_RESPONSE:
            raise ValueError(f"Task type must be {TaskType.MULTIPLE_RESPONSE}")
        return self


class ProgrammingTaskResult(TaskResultPublic):
    result: list[TestcaseResult] | None  # TODO: handle this one properly

    @model_validator(mode="after")
    def validate_task_type(self) -> Self:
        if not self.task_type == TaskType.PROGRAMMING:
            raise ValueError(f"Task type must be {TaskType.PROGRAMMING}")
        return self


class ShortAnswerTaskResult(TaskResultPublic):
    result: str | None  # TODO: check this one

    @model_validator(mode="after")
    def validate_task_type(self) -> Self:
        if not self.task_type == TaskType.SHORT_ANSWER:
            raise ValueError(f"Task type must be {TaskType.SHORT_ANSWER}")
        return self


type TaskResult = (
    MultipleChoiceTaskResult
    | MultipleResponseTaskResult
    | ProgrammingTaskResult
    | ShortAnswerTaskResult
)
