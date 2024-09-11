import argparse
import os
import sys
from enum import Enum

from pydantic import BaseModel


class TaskType(str, Enum):
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    MULTIPLE_RESPONSE = "MULTIPLE_RESPONSE"
    SHORT_ANSWER = "SHORT_ANSWER"
    PROGRAMMING = "PROGRAMMING"


class Task(BaseModel, extra="allow"):
    id: int
    type: TaskType
    autograde: bool = True


class MultipleChoiceTask(Task):
    question: str
    choices: list[str]

    input: int

    def run(self, expected: int) -> bool:
        return expected == self.input


class MultipleResponseTask(Task):
    question: str
    choices: list[str]

    input: set[int]

    def run(self, expected: set[int]) -> tuple[int, int, int]:
        correct = len(expected & self.input)
        incorrect = len(expected - self.input)
        return correct, incorrect, len(self.choices)


class ShortAnswerTask(Task):
    question: str
    autograde: bool = False

    input: str


class ProgrammingLanguage(str, Enum):
    PYTHON = "PYTHON"


class ProgrammingEnvironment(BaseModel):
    language: ProgrammingLanguage
    options: dict[str, str]
    time_limit: int  # in seconds
    memory_limit: int  # in MB


class File(BaseModel):
    file_name: str
    content: str


class StepType(str, Enum):
    PY_RUN_FUNCTION = "PY_RUN_FUNCTION"


class Step(BaseModel):
    type: StepType


class PyRunFunctionStep(Step):
    function_name: str
    arguments: list[str]
    keyword_arguments: dict[str, str]


class Testcase(BaseModel):
    id: int
    steps: list[Step]


class ProgrammingTask(Task):
    question: str
    environment: ProgrammingEnvironment
    templates: list[File]
    testcases: list[Testcase]

    input: list[File]

    def run(self, expected: str) -> bool:
        raise NotImplementedError()


class Project(BaseModel):
    name: str
    description: str
    tasks: list[Task]


if __name__ == "__main__":

    def exit_if(predicate: bool, err_msg: str, exit_code: int = 1) -> None:
        if predicate:
            print(err_msg, file=sys.stderr)
            exit(exit_code)

    parser = argparse.ArgumentParser()
    parser.add_argument("submission", type=str, help="Path to the submission file")
    parser.add_argument("answer", type=str, help="Path to the answer file")

    args = parser.parse_args()
    exit_if(not os.path.exists(args.submission), "Submission file not found!")
    exit_if(not os.path.exists(args.answer), "Answer file not found!")

    with open(args.submission) as def_fp:
        project: Project = Project.model_validate_json(def_fp.read())
