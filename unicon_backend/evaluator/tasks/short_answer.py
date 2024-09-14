from typing import Any
from unicon_backend.evaluator.tasks.base import Task


class ShortAnswerTask(Task[str, bool, str]):
    question: str
    autograde: bool = False

    input: str

    def run(self, _: str) -> bool:
        return False

    def validate_answer(self, answer: Any) -> str:
        if not isinstance(answer, str):
            raise ValueError("Answer must be a string")
        return answer
