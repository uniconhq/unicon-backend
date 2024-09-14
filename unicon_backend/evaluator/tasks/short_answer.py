from typing import Any, ClassVar
from unicon_backend.evaluator.tasks.base import (
    Task,
    TaskEvaluationResult,
    TaskEvaluationStatus,
)


class ShortAnswerTask(Task[str, bool, str]):
    question: str
    autograde: bool = False

    input: str

    answer_validate_help: ClassVar[str] = (
        "Answer must be a string representing the short answer."
    )

    def run(self, expected: str) -> TaskEvaluationResult[bool]:
        if self.autograde is False:
            return TaskEvaluationResult(
                status=TaskEvaluationStatus.SKIPPED, result=None
            )

        return TaskEvaluationResult(
            status=TaskEvaluationStatus.SUCCESS, result=expected == self.input
        )

    def validate_answer(self, answer: Any) -> str:
        if not isinstance(answer, str):
            raise ValueError(self.answer_validate_help)
        return answer
