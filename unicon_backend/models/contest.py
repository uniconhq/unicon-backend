from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg
import sqlalchemy.orm as sa_orm
from sqlmodel import Field, ForeignKeyConstraint, Relationship, SQLModel

if TYPE_CHECKING:
    from unicon_backend.evaluator.contest import Definition
    from unicon_backend.evaluator.tasks.base import Task


class TaskType(str, Enum):
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE_TASK"
    MULTIPLE_RESPONSE = "MULTIPLE_RESPONSE_TASK"
    SHORT_ANSWER = "SHORT_ANSWER_TASK"
    PROGRAMMING = "PROGRAMMING_TASK"


class TaskEvalStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PENDING = "PENDING"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class SubmissionStatus(str, Enum):
    Pending = "PENDING"
    Ok = "OK"


class DefinitionORM(SQLModel, table=True):
    __tablename__ = "definition"

    id: int = Field(primary_key=True)
    name: str
    description: str

    tasks: sa_orm.Mapped[list["TaskORM"]] = Relationship(back_populates="definition")

    def update(self, definition: "Definition") -> None:
        self.name = definition.name
        self.description = definition.description

        # Remove existing tasks and add new ones
        self.tasks.clear()
        self.tasks.extend([TaskORM.from_task(task) for task in definition.tasks])

    @classmethod
    def from_definition(cls, definition: "Definition") -> "DefinitionORM":
        tasks_orm: list[TaskORM] = [TaskORM.from_task(task) for task in definition.tasks]
        return cls(name=definition.name, description=definition.description, tasks=tasks_orm)


class TaskORM(SQLModel, table=True):
    __tablename__ = "task"

    id: int = Field(primary_key=True)
    type: TaskType = Field(sa_column=sa.Column(pg.ENUM(TaskType), nullable=False))
    autograde: bool
    other_fields: dict = Field(default_factory=dict, sa_column=sa.Column(pg.JSONB))
    definition_id: int = Field(foreign_key="definition.id", primary_key=True)

    definition: sa_orm.Mapped[DefinitionORM] = Relationship(back_populates="tasks")

    @classmethod
    def from_task(cls, task: "Task") -> "TaskORM":
        def _convert_task_to_orm(id: int, type: TaskType, autograde: bool, **other_fields):
            return TaskORM(id=id, type=type, autograde=autograde, other_fields=other_fields)

        return _convert_task_to_orm(**task.model_dump(serialize_as_any=True))


class SubmissionORM(SQLModel, table=True):
    __tablename__ = "submission"

    id: int = Field(primary_key=True)
    definition_id: int = Field(foreign_key="definition.id")
    status: SubmissionStatus = Field(sa_column=sa.Column(pg.ENUM(SubmissionStatus), nullable=False))
    submitted_at: datetime = Field(
        sa_column=sa.Column(
            pg.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        )
    )

    # TODO: split this to one more table
    other_fields: dict = Field(default_factory=dict, sa_column=sa.Column(pg.JSONB))

    task_results: sa_orm.Mapped[list["TaskResultORM"]] = Relationship(back_populates="submission")


class TaskResultORM(SQLModel, table=True):
    __tablename__ = "task_result"
    __table_args__ = (
        ForeignKeyConstraint(["definition_id", "task_id"], ["task.definition_id", "task.id"]),
    )

    id: int = Field(primary_key=True)
    submission_id: int = Field(foreign_key="submission.id")
    definition_id: int
    task_id: int

    started_at: datetime = Field(
        sa_column=sa.Column(
            pg.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        )
    )
    completed_at: datetime | None = Field(
        sa_column=sa.Column(pg.TIMESTAMP(timezone=True), nullable=True)
    )

    # NOTE: Unique identifier for a worker job that evaluates the task
    job_id: str | None = Field(nullable=True, unique=True)

    status: TaskEvalStatus = Field(sa_column=sa.Column(pg.ENUM(TaskEvalStatus), nullable=False))
    # TODO: Handle non-JSON result types for non-programming tasks
    result: dict = Field(default_factory=dict, sa_column=sa.Column(pg.JSONB))
    error: str | None = Field(nullable=True)

    submission: sa_orm.Mapped[SubmissionORM] = Relationship(back_populates="task_results")
