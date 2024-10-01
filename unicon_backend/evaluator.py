import argparse
import os
import sys
from collections.abc import Callable
from io import TextIOWrapper

from unicon_backend.evaluator.contest import Definition, ExpectedAnswers, UserInputs
from unicon_backend.logger import setup_rich_logger


def exit_if(predicate: bool, err_msg: str, exit_code: int = 1) -> None:
    if predicate:
        print(err_msg, file=sys.stderr)
        exit(exit_code)


def arg_file_type(parser: argparse.ArgumentParser) -> Callable[[str], TextIOWrapper]:
    def is_file(arg: str) -> TextIOWrapper:
        if not os.path.exists(arg):
            parser.error(f"{arg} does not exist!")
        return open(arg)  # noqa: SIM115

    return is_file


if __name__ == "__main__":
    setup_rich_logger()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "definition",
        type=arg_file_type(parser),
        help="Path to the contest definition file",
    )
    parser.add_argument(
        "submission", type=arg_file_type(parser), help="Path to the submission file"
    )
    parser.add_argument("answer", type=arg_file_type(parser), help="Path to the answer file")
    parser.add_argument("--task-id", type=int, help="Run only the task with the specified ID")

    args = parser.parse_args()

    definition: Definition = Definition.model_validate_json(args.definition.read())
    user_inputs: UserInputs = UserInputs.model_validate_json(args.submission.read())
    expected_answers: ExpectedAnswers = ExpectedAnswers.model_validate_json(args.answer.read())

    definition.run(user_inputs, expected_answers, task_id=args.task_id)
