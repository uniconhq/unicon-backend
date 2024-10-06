from datetime import datetime
from enum import Enum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from unicon_backend.models.base import Base


class DefinitionORM(Base):
    __tablename__ = "definition"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str]

    tasks: Mapped[list["TaskORM"]] = relationship(back_populates="definition")


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


class TaskORM(Base):
    __tablename__ = "task"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[TaskType]
    autograde: Mapped[bool]
    other_fields: Mapped[dict] = mapped_column(JSONB)
    definition_id: Mapped[int] = mapped_column(sa.ForeignKey("definition.id"), primary_key=True)

    definition: Mapped[DefinitionORM] = relationship(back_populates="tasks")


class SubmissionStatus(str, Enum):
    Pending = "PENDING"
    Ok = "OK"


class SubmissionORM(Base):
    __tablename__ = "submission"

    id: Mapped[int] = mapped_column(primary_key=True)
    definition_id = mapped_column(sa.ForeignKey("definition.id"))
    status: Mapped[SubmissionStatus]
    submitted_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    # TODO: split this to one more table
    other_fields: Mapped[dict] = mapped_column(JSONB)

    task_results: Mapped[list["TaskResultORM"]] = relationship(back_populates="submission")


class TaskResultORM(Base):
    __tablename__ = "task_result"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(sa.ForeignKey("submission.id"))
    definition_id: Mapped[int]
    task_id: Mapped[int]

    started_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    # NOTE: Unique identifier for a worker job that evaluates the task
    job_id: Mapped[str | None] = mapped_column(unique=True, nullable=True)

    status: Mapped[TaskEvalStatus]
    result: Mapped[dict] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(nullable=True)

    submission: Mapped[SubmissionORM] = relationship(back_populates="task_results")

    __table_args__ = (
        sa.ForeignKeyConstraint(["definition_id", "task_id"], [TaskORM.definition_id, TaskORM.id]),
    )
