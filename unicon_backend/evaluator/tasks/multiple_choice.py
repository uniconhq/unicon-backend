from typing import Any

from pydantic import BaseModel, RootModel

from unicon_backend.evaluator.tasks.base import Task, TaskEvalResult, TaskEvalStatus


class MultipleChoiceTask(Task[int, bool, int]):
    question: str
    choices: list[str]

    def run(self, user_input: int, expected_answer: int) -> TaskEvalResult[bool]:
        return TaskEvalResult(
            status=TaskEvalStatus.SUCCESS, result=user_input == expected_answer
        )

    def validate_user_input(self, user_input: Any) -> int:
        return RootModel[int].model_validate(user_input).root

    def validate_expected_answer(self, expected_answer: Any) -> int:
        validated = RootModel[int].model_validate(expected_answer).root

        # Verify that the expected answer is within the range of choices
        if validated < 0 or validated >= len(self.choices):
            raise ValueError("Expected answer must be within the range of choices")

        return validated


class MultipleResponseTaskResult(BaseModel):
    correct_choices: set[int]
    incorrect_choices: set[int]
    num_choices: int


class MultipleResponseTask(Task[set[int], MultipleResponseTaskResult, set[int]]):
    question: str
    choices: list[str]

    def run(
        self, user_input: set[int], expected_answer: set[int]
    ) -> TaskEvalResult[MultipleResponseTaskResult]:
        return TaskEvalResult(
            status=TaskEvalStatus.SUCCESS,
            result=MultipleResponseTaskResult(
                correct_choices=user_input & expected_answer,
                incorrect_choices=user_input - expected_answer,
                num_choices=len(expected_answer),
            ),
        )

    def validate_user_input(self, user_input: Any) -> set[int]:
        return RootModel[set[int]].model_validate(user_input).root

    def validate_expected_answer(self, expected_answer: Any) -> set[int]:
        validated = RootModel[set[int]].model_validate(expected_answer).root

        # Verify that choices in the expected answer are within the range of choices
        if not all(0 <= choice < len(self.choices) for choice in validated):
            raise ValueError("Expected answer must be within the range of choices")

        return validated
