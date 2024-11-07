from datetime import datetime
from enum import Enum

import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg
from sqlmodel import Field, ForeignKeyConstraint, Relationship, SQLModel


class DefinitionORM(SQLModel, table=True):
    __tablename__ = "definition"

    id: int = Field(primary_key=True)
    name: str
    description: str

    tasks: list["TaskORM"] = Relationship(back_populates="definition")


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


class TaskORM(SQLModel, table=True):
    __tablename__ = "task"

    id: int = Field(primary_key=True)
    type: TaskType = Field(sa_column=sa.Column(pg.ENUM(TaskType), nullable=False))
    autograde: bool
    other_fields: dict = Field(default_factory=dict, sa_column=sa.Column(pg.JSONB))
    definition_id: int = Field(foreign_key="definition.id", primary_key=True)

    definition: DefinitionORM = Relationship(back_populates="tasks")


class SubmissionStatus(str, Enum):
    Pending = "PENDING"
    Ok = "OK"


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

    task_results: list["TaskResultORM"] = Relationship(back_populates="submission")


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
    result: dict = Field(default_factory=dict, sa_column=sa.Column(pg.JSONB))
    error: str | None = Field(nullable=True)

    submission: SubmissionORM = Relationship(back_populates="task_results")
