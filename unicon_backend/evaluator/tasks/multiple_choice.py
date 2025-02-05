from functools import cached_property
from typing import Any, Literal, Self

from pydantic import BaseModel, RootModel, model_validator

from unicon_backend.evaluator.tasks.base import Task, TaskEvalResult, TaskEvalStatus, TaskType


class Choice(BaseModel):
    id: str  # uuid generated on the frontend
    order_index: int
    text: str


class MultipleChoiceTask(Task[int, RootModel[bool]]):
    type: Literal[TaskType.MULTIPLE_CHOICE]
    question: str
    choices: list[Choice]
    expected_answer: str

    @model_validator(mode="after")
    def check_expected_answer_is_valid(self) -> Self:
        if not self.expected_answer in [choice.id for choice in self.choices]:
            raise ValueError("The answer must match one of the provided choice IDs.")
        return self

    def run(self, user_input: int) -> TaskEvalResult[RootModel[bool]]:
        return TaskEvalResult(
            task_id=self.id,
            status=TaskEvalStatus.SUCCESS,
            result=RootModel[bool](user_input == self.expected_answer),
        )

    def validate_user_input(self, user_input: Any) -> int:
        return RootModel[str].model_validate(user_input).root


class MultipleResponseTaskResult(BaseModel):
    correct_choices: set[int]
    incorrect_choices: set[int]
    num_choices: int


class MultipleResponseTask(Task[set[int], MultipleResponseTaskResult]):
    type: Literal[TaskType.MULTIPLE_RESPONSE]
    question: str
    choices: list[Choice]
    expected_answer: list[str]

    @cached_property
    def valid_choice_ids(self) -> set[int]:
        return {choice.id for choice in self.choices}

    @model_validator(mode="after")
    def check_correct_choices_is_valid(self) -> Self:
        if len(self.expected_answer) != len(set(self.expected_answer)):
            raise ValueError("Correct choices must be unique")

        expected_answer = set(self.expected_answer)

        if not expected_answer.issubset(self.valid_choice_ids):
            raise ValueError("The answer(s) must be within the given choice IDs.")
        return self

    def run(self, user_input: set[str]) -> TaskEvalResult[MultipleResponseTaskResult]:
        expected_answer = set(self.expected_answer)

        # This is necessary as formerly valid user input may no longer be valid after a task update.
        # e.g. deleting of a choice that the user picked.
        user_input = user_input & self.valid_choice_ids

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
