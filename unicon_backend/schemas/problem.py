from unicon_backend.evaluator.problem import Problem


class ProblemPublic(Problem):
    # permissions
    edit: bool
    make_submission: bool
