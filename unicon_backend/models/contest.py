from enum import Enum

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from unicon_backend.models.base import Base


class TaskType(str, Enum):
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE_TASK"
    MULTIPLE_RESPONSE = "MULTIPLE_RESPONSE_TASK"
    SHORT_ANSWER = "SHORT_ANSWER_TASK"
    PROGRAMMING = "PROGRAMMING_TASK"


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

    task_submission_id: Mapped[str | None] = mapped_column(unique=True, nullable=True)
    other_fields: Mapped[dict] = mapped_column(JSONB)

    submission: Mapped[SubmissionORM] = relationship(back_populates="task_results")
