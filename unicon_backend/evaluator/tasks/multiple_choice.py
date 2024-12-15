from typing import Any, Literal, Self

from pydantic import BaseModel, RootModel, model_validator

from unicon_backend.evaluator.tasks.base import Task, TaskEvalResult, TaskEvalStatus, TaskType


class MultipleChoiceTask(Task[int, RootModel[bool]]):
    type: Literal[TaskType.MULTIPLE_CHOICE]
    question: str
    choices: list[str]
    expected_answer: int

    @model_validator(mode="after")
    def check_expected_answer_is_valid(self) -> Self:
        if self.expected_answer < 0 or self.expected_answer >= len(self.choices):
            raise ValueError("Expected answer must be within the range of choices")
        return self

    def run(self, user_input: int) -> TaskEvalResult[RootModel[bool]]:
        return TaskEvalResult(
            task_id=self.id,
            status=TaskEvalStatus.SUCCESS,
            result=RootModel[bool](user_input == self.expected_answer),
        )

    def validate_user_input(self, user_input: Any) -> int:
        return RootModel[int].model_validate(user_input).root


class MultipleResponseTaskResult(BaseModel):
    correct_choices: set[int]
    incorrect_choices: set[int]
    num_choices: int


class MultipleResponseTask(Task[set[int], MultipleResponseTaskResult]):
    type: Literal[TaskType.MULTIPLE_RESPONSE]
    question: str
    choices: list[str]
    expected_answer: list[int]

    @model_validator(mode="after")
    def check_correct_choices_is_valid(self) -> Self:
        if len(self.expected_answer) != len(set(self.expected_answer)):
            raise ValueError("Correct choices must be unique")

        if not all(0 <= choice < len(self.choices) for choice in self.expected_answer):
            raise ValueError("Expected answer must be within the range of choices")
        return self

    def run(self, user_input: set[int]) -> TaskEvalResult[MultipleResponseTaskResult]:
        expected_answer = set(self.expected_answer)
        return TaskEvalResult(
            task_id=self.id,
            status=TaskEvalStatus.SUCCESS,
            result=MultipleResponseTaskResult(
                correct_choices=user_input & expected_answer,
                incorrect_choices=user_input - expected_answer,
                num_choices=len(expected_answer),
            ),
        )

    def validate_user_input(self, user_input: Any) -> set[int]:
        return RootModel[set[int]].model_validate(user_input).root
