from pydantic import BaseModel, ConfigDict

from unicon_backend.evaluator.problem import Problem


class MiniProblemPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ProblemPublic(Problem):
    # permissions

    edit: bool
    make_submission: bool
