from typing import Any, Literal, Self

from pydantic import RootModel, model_validator

from unicon_backend.evaluator.tasks.base import Task, TaskEvalResult, TaskEvalStatus, TaskType


class ShortAnswerTask(Task[str, RootModel[bool]]):
    type: Literal[TaskType.SHORT_ANSWER]
    autograde: bool = False
    expected_answer: str | None = None

    @model_validator(mode="after")
    def check_expected_answer_is_valid(self) -> Self:
        if self.autograde and self.expected_answer is None:
            raise ValueError("Expected answer must not be None if autograde is enabled")
        return self

    def run(self, user_input: str) -> TaskEvalResult[RootModel[bool]]:
        if self.autograde is False:
            return TaskEvalResult(task_id=self.id, status=TaskEvalStatus.SKIPPED, result=None)

        return TaskEvalResult(
            task_id=self.id,
            status=TaskEvalStatus.SUCCESS,
            result=RootModel[bool](
                (self.expected_answer is not None) and (self.expected_answer == user_input)
            ),
        )

    def validate_user_input(self, user_input: Any) -> str:
        return RootModel[str].model_validate(user_input).root
