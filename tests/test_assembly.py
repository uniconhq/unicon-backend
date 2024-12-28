import json
import subprocess
from pathlib import Path
from typing import TypedDict

import pytest
import yaml
from pydantic import RootModel

from unicon_backend.evaluator.problem import Problem
from unicon_backend.evaluator.tasks.base import TaskType
from unicon_backend.evaluator.tasks.programming.base import RequiredInput
from unicon_backend.runner import RunnerProgram


def execute_program(program: RunnerProgram, temp_dir: Path) -> tuple[int, str, str]:
    """Simplistic executor - do not run unsafe code (e.g arbitrary code execution) with it."""
    for file in program.files:
        file_path = temp_dir / file.name
        file_path.write_text(file.content)

    proc = subprocess.run(["python", str(temp_dir / program.entrypoint)], capture_output=True)
    return proc.returncode, proc.stdout.decode(), proc.stderr.decode()


class ExpectedResult(TypedDict):
    returncode: int
    stdout: str


class Input(TypedDict):
    file: str
    result: ExpectedResult


class Definition(TypedDict):
    definition: str
    inputs: list[Input]


with open("./tests/inputs.yaml") as defn_file:
    testcases = yaml.safe_load(defn_file)


@pytest.mark.parametrize("testcase", testcases)
def test_assembly(testcase: Definition, tmp_path):
    with open(testcase["definition"]) as defn_file:
        defn = Problem.model_validate_json(defn_file.read())

    for input in testcase["inputs"]:
        with open(input["file"]) as ans_file:
            user_inputs = json.loads(ans_file.read())["user_inputs"]

        for user_input_dict in user_inputs:
            user_input = (
                RootModel[list[RequiredInput]].model_validate(user_input_dict["value"]).root
            )

            task = defn.task_index[user_input_dict["task_id"]]
            assert task.type == TaskType.PROGRAMMING

            programs = task._get_runner_programs(user_input)
            returncode, stdout, stderr = execute_program(programs[0], tmp_path)
            assert returncode == input["result"]["returncode"]
            assert stdout == input["result"]["stdout"]
            assert stderr == ""
