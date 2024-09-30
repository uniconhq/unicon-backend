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


class Definition(Base):
    __tablename__ = "defintion"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str]

    tasks: Mapped[list["Task"]] = relationship(back_populates="definition")


class Task(Base):
    __tablename__ = "task"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[TaskType]
    autograde: Mapped[bool]
    metadata: Mapped[JSONB]
    definition_id: Mapped[int] = mapped_column(ForeignKey("definition.id"))

    definition: Mapped[Definition] = relationship(back_populates="tasks")
