import argparse
import os
import sys
from io import TextIOWrapper
from typing import Callable

from unicon_backend.evaluator.project import (
    Project,
    ProjectExpectedAnswers,
    ProjectUserInputs,
)


def exit_if(predicate: bool, err_msg: str, exit_code: int = 1) -> None:
    if predicate:
        print(err_msg, file=sys.stderr)
        exit(exit_code)


def arg_file_type(parser: argparse.ArgumentParser) -> Callable[[str], TextIOWrapper]:
    def is_file(arg: str) -> TextIOWrapper:
        if not os.path.exists(arg):
            parser.error(f"{arg} does not exist!")
        return open(arg, "r")

    return is_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "definition",
        type=arg_file_type(parser),
        help="Path to the project definition file",
    )
    parser.add_argument(
        "submission", type=arg_file_type(parser), help="Path to the submission file"
    )
    parser.add_argument(
        "answer", type=arg_file_type(parser), help="Path to the answer file"
    )
    parser.add_argument(
        "--task-id", type=int, help="Run only the task with the specified ID"
    )

    args = parser.parse_args()

    project: Project = Project.model_validate_json(args.definition.read())
    user_inputs: ProjectUserInputs = ProjectUserInputs.model_validate_json(
        args.submission.read()
    )
    expected_answers: ProjectExpectedAnswers = (
        ProjectExpectedAnswers.model_validate_json(args.answer.read())
    )

    project.run(user_inputs, expected_answers, task_id=args.task_id)
