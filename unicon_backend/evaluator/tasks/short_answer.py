from unicon_backend.evaluator.tasks.base import Task


class ShortAnswerTask(Task[str, bool]):
    question: str
    autograde: bool = False

    input: str

    def run(self, _: str) -> bool:
        return False
