from typing import Final

from unicon_backend.evaluator.tasks.base import Task, TaskEvalResult, TaskEvalStatus, TaskType

# NOTE: We import all task types here to initialize their declarations for `CustomBaseModel`
from unicon_backend.evaluator.tasks.multiple_choice import MultipleChoiceTask, MultipleResponseTask
from unicon_backend.evaluator.tasks.programming.base import ProgrammingTask
from unicon_backend.evaluator.tasks.short_answer import ShortAnswerTask

task_classes: Final[dict[TaskType, type[Task]]] = {
    TaskType.MULTIPLE_CHOICE: MultipleChoiceTask,
    TaskType.MULTIPLE_RESPONSE: MultipleResponseTask,
    TaskType.PROGRAMMING: ProgrammingTask,
    TaskType.SHORT_ANSWER: ShortAnswerTask,
}

__all__ = [
    "Task",
    "TaskEvalStatus",
    "TaskEvalResult",
    "TaskType",
    "MultipleChoiceTask",
    "MultipleResponseTask",
    "ShortAnswerTask",
    "ProgrammingTask",
]
