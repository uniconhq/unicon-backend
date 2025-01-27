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


class TaskOrder(BaseModel):
    id: int
    order_index: int


class ProblemUpdate(BaseModel):
    name: str
    restricted: bool
    description: str
    task_order: list[TaskOrder]


class TaskUpdate(BaseModel):
    task: Task
    rerun: bool


class ParseRequest(BaseModel):
    content: str


class ParsedFunction(BaseModel):
    name: str
    args: list[str]
    kwargs: list[str]
    star_args: bool
    star_kwargs: bool
