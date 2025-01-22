from pathlib import Path
from typing import TypedDict

import pytest
import yaml

from unicon_backend.evaluator.problem import Problem
from unicon_backend.evaluator.tasks.base import TaskType


class AssemblyTestcase(TypedDict):
    definition: str
    """File path to the problem definition"""

    output: list[list[str]]
    """List of code outputs per testcase. Non programming tasks have an empty list and are ignored by the test."""


TEST_FILE_DIR = Path(__file__).parent
TEST_INPUT_FILE = TEST_FILE_DIR / "inputs.yaml"
with open(TEST_INPUT_FILE) as defn_file:
    testcases = yaml.safe_load(defn_file)


@pytest.mark.parametrize("testcase", testcases)
def test_assembly(testcase: AssemblyTestcase):
    with Path(testcase["definition"]).open() as defn_file:
        defn = Problem.model_validate_json(defn_file.read())

    for task_index, task in enumerate(defn.tasks):
        if task.type != TaskType.PROGRAMMING:
            continue

        user_input_step = task.create_input_step(task.required_inputs)

        for index, task_tc in enumerate(task.testcases):
            assembled_prog = task_tc.run(user_input_step)
            expected_output = testcase["output"][task_index][index]
            assert assembled_prog.code == expected_output
