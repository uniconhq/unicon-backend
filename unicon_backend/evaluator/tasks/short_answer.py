from typing import Any, Literal

from pydantic import RootModel

from unicon_backend.evaluator.tasks.base import Task, TaskEvalResult, TaskEvalStatus, TaskType


class ShortAnswerTask(Task[str, RootModel[bool], str]):
    type: Literal[TaskType.SHORT_ANSWER]
    question: str
    autograde: bool = False

    def run(self, user_input: str, expected_answer: str) -> TaskEvalResult[RootModel[bool]]:
        if self.autograde is False:
            return TaskEvalResult(task_id=self.id, status=TaskEvalStatus.SKIPPED, result=None)

        return TaskEvalResult(
            task_id=self.id,
            status=TaskEvalStatus.SUCCESS,
            result=RootModel[bool](
                (expected_answer is not None) and (expected_answer == user_input)
            ),
        )

    def validate_user_input(self, user_input: Any) -> str:
        return RootModel[str].model_validate(user_input).root

    def validate_expected_answer(self, expected_answer: Any) -> str:
        validated = RootModel[str].model_validate(expected_answer).root

        # Verify that if autograde is enabled, the expected answer is not None
        if self.autograde and validated is None:
            raise ValueError("Expected answer must not be None if autograde is enabled")

        return validated
