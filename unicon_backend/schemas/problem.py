from pydantic import BaseModel, ConfigDict

from unicon_backend.evaluator.problem import Problem, Task


class MiniProblemPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ProblemPublic(Problem):
    # permissions

    edit: bool
    make_submission: bool


class TaskUpdate(BaseModel):
    task: Task
    rerun: bool
