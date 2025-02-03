from pydantic import BaseModel

from unicon_backend.evaluator.problem import Problem, Task


class ProblemPublic(Problem):
    # permissions

    edit: bool
    make_submission: bool


class TaskUpdate(BaseModel):
    task: Task
    rerun: bool
