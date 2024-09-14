from typing import Any, ClassVar
from unicon_backend.evaluator.tasks.base import (
    Task,
    TaskEvaluationResult,
    TaskEvaluationStatus,
)
from pydantic import BaseModel


class MultipleChoiceTask(Task[int, bool, int]):
    question: str
    choices: list[str]

    input: int

    answer_validate_help: ClassVar[str] = "\n".join(
        [
            "Answer must be an integer representing the index of the correct choice (zero-indexed).",
            "  e.g. If [A, B, C] is the list of choices, the correct choice is B, the answer should be 1.",
            "Note that the given answer needs to be within the range of the number of choices.",
            "  e.g. If [A, B, C] is the list of choices, the answer should be 0, 1, or 2.",
        ]
    )

    def run(self, expected: int) -> TaskEvaluationResult[bool]:
        return TaskEvaluationResult(
            status=TaskEvaluationStatus.SUCCESS, result=expected == self.input
        )

    def validate_answer(self, answer: Any) -> int:
        if isinstance(answer, int) or (isinstance(answer, str) and answer.isnumeric()):
            answer = int(answer)
            in_range = 0 <= answer < len(self.choices)
            if in_range:
                return answer

        raise ValueError(self.answer_validate_help)


class MultipleResponseTaskResult(BaseModel):
    correct_choices: set[int]
    incorrect_choices: set[int]
    num_choices: int


class MultipleResponseTask(Task[set[int], MultipleResponseTaskResult, set[int]]):
    question: str
    choices: list[str]

    input: set[int]

    answer_validate_help: ClassVar[str] = "\n".join(
        [
            "Answer must be a list or set of integers representing the indices of the correct choices (zero-indexed).",
            "  e.g. If [A, B, C] is the list of choices, the correct choices are A and C, the answer should be [0, 2].",
            "Note that the given answer needs to be within the range of the number of choices.",
            "  e.g. If [A, B, C] is the list of choices, the answer should be a subset of [0, 1, 2].",
        ]
    )

    def run(
        self, expected: set[int]
    ) -> TaskEvaluationResult[MultipleResponseTaskResult]:
        return TaskEvaluationResult(
            status=TaskEvaluationStatus.SUCCESS,
            result=MultipleResponseTaskResult(
                correct_choices=self.input & expected,
                incorrect_choices=self.input - expected,
                num_choices=len(self.choices),
            ),
        )

    def validate_answer(self, answer: Any) -> set[int]:
        if isinstance(answer, (list, set)):
            answer = set(answer)
            all_ints = all(isinstance(choice, int) for choice in answer)
            all_in_range = all(0 <= choice < len(self.choices) for choice in answer)
            if all_ints and all_in_range:
                return answer

        raise ValueError(self.answer_validate_help)
