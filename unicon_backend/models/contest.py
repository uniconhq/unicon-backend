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
