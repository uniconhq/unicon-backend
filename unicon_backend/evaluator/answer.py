from pydantic import BaseModel

from unicon_backend.evaluator.tasks.programming import File


class Answer(BaseModel):
    artifacts: list[File]
