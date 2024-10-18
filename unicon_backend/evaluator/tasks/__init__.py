from unicon_backend.evaluator.tasks.base import Task, TaskEvalResult, TaskEvalStatus, TaskType

# NOTE: We import all task types here to initialize their declarations for `CustomBaseModel`
from unicon_backend.evaluator.tasks.multiple_choice import MultipleChoiceTask, MultipleResponseTask
from unicon_backend.evaluator.tasks.programming.task import ProgrammingTask
from unicon_backend.evaluator.tasks.short_answer import ShortAnswerTask

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
