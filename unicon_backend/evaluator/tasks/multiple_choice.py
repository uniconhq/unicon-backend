from typing import Any
from unicon_backend.evaluator.tasks.base import Task


class MultipleChoiceTask(Task[int, bool, int]):
    question: str
    choices: list[str]

    input: int

    def run(self, expected: int) -> bool:
        return expected == self.input

    def validate_answer(self, answer: Any) -> int:
        match answer:
            case int():
                return answer
            case str():
                if answer.isnumeric():
                    return int(answer)
                raise ValueError("Answer must be an integer")
            case _:
                raise ValueError("Answer must be an integer")


class MultipleResponseTask(Task[set[int], tuple[int, int, int], set[int]]):
    question: str
    choices: list[str]

    input: set[int]

    def run(self, expected: set[int]) -> tuple[int, int, int]:
        correct = len(expected & self.input)
        incorrect = len(expected - self.input)
        return correct, incorrect, len(self.choices)

    def validate_answer(self, answer: Any) -> set[int]:
        match answer:
            case set():
                return answer
            case list():
                return set(answer)
            case _:
                raise ValueError("Answer must be a list or set of integers")
