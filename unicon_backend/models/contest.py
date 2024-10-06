from enum import Enum

from sqlalchemy import ForeignKey, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from unicon_backend.evaluator.tasks import TaskEvalStatus, TaskType
from unicon_backend.models.base import Base


class DefinitionORM(Base):
    __tablename__ = "definition"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str]

    tasks: Mapped[list["TaskORM"]] = relationship(back_populates="definition")


class TaskORM(Base):
    __tablename__ = "task"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[TaskType]
    autograde: Mapped[bool]
    other_fields: Mapped[dict] = mapped_column(JSONB)
    definition_id: Mapped[int] = mapped_column(ForeignKey("definition.id"), primary_key=True)

    definition: Mapped[DefinitionORM] = relationship(back_populates="tasks")


class SubmissionStatus(str, Enum):
    Pending = "PENDING"
    Ok = "OK"


class SubmissionORM(Base):
    __tablename__ = "submission"

    id: Mapped[int] = mapped_column(primary_key=True)
    definition_id = mapped_column(ForeignKey("definition.id"))
    status: Mapped[SubmissionStatus]

    # TODO: split this to one more table
    other_fields: Mapped[dict] = mapped_column(JSONB)

    task_results: Mapped[list["TaskResultORM"]] = relationship(back_populates="submission")


class TaskResultORM(Base):
    __tablename__ = "task_result"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submission.id"))
    definition_id: Mapped[int]
    task_id: Mapped[int]

    # NOTE: Unique identifier for a worker job that evaluates the task
    job_id: Mapped[str | None] = mapped_column(unique=True, nullable=True)

    status: Mapped[TaskEvalStatus]
    result: Mapped[dict] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(nullable=True)

    submission: Mapped[SubmissionORM] = relationship(back_populates="task_results")

    __table_args__ = (
        ForeignKeyConstraint(["definition_id", "task_id"], [TaskORM.definition_id, TaskORM.id]),
    )
