from unicon_backend.evaluator.tasks.base import Task


class MultipleChoiceTask(Task[int, bool]):
    question: str
    choices: list[str]

    input: int

    def run(self, expected: int) -> bool:
        return expected == self.input


class MultipleResponseTask(Task[set[int], tuple[int, int, int]]):
    question: str
    choices: list[str]

    input: set[int]

    def run(self, expected: set[int]) -> tuple[int, int, int]:
        correct = len(expected & self.input)
        incorrect = len(expected - self.input)
        return correct, incorrect, len(self.choices)
