from collections.abc import Iterable
from logging import getLogger
from typing import Any

from pydantic import BaseModel, RootModel

from unicon_backend.evaluator.tasks import Task, TaskEvalResult, TaskEvalStatus
from unicon_backend.evaluator.tasks.programming.artifact import File, PrimitiveData
from unicon_backend.evaluator.tasks.programming.runner import (
    RunnerEnvironment,
    RunnerPackage,
    RunnerRequest,
    SubmissionId,
)
from unicon_backend.evaluator.tasks.programming.steps import (
    ComputeGraph,
    InputStep,
    Program,
    StepSocket,
    StepType,
)
from unicon_backend.workers import task_publisher

logger = getLogger(__name__)

USER_INPUT_STEP_ID: int = 0


def assemble_program(program: Program, indent_symbol: str = " " * 2) -> str:
    def flatten(xs, indent_level=-1):
        for x in xs:
            if isinstance(x, Iterable) and not isinstance(x, str):
                yield ""  # Add a blank line between different parts of the program
                yield from flatten(x, indent_level + 1)
            else:
                yield f"{indent_symbol * indent_level}{x}"

    return "\n".join(flatten(program))


class Testcase(ComputeGraph):
    id: int


class RequiredInput(BaseModel):
    id: str
    data: PrimitiveData | File


class ExpectedAnswer(BaseModel):
    testcase_id: int
    step_id: int
    expected_answer: Any


class ProgrammingTask(Task[list[RequiredInput], SubmissionId, list[ExpectedAnswer]]):
    question: str
    environment: RunnerEnvironment
    required_inputs: list[RequiredInput]
    testcases: list[Testcase]

    def run(self, user_inputs: list[RequiredInput], _) -> TaskEvalResult[SubmissionId]:
        # Check if all required inputs are provided
        for required_input in self.required_inputs:
            if not any(required_input.id == user_input.id for user_input in user_inputs):
                raise ValueError(f"Required input {required_input.id} not provided")

        # Transform user input into InputStep
        # This is so that we simply treat it as a node in the graph
        # NOTE: We assume that the id of user inputs is always 0
        user_input_step: InputStep = InputStep(
            id=USER_INPUT_STEP_ID,
            inputs=[],
            outputs=[
                StepSocket(id=str(user_input.id), data=user_input.data)
                for user_input in user_inputs
            ],
            type=StepType.INPUT,
        )

        user_input_files: list[File] = [
            user_input.data for user_input in user_inputs if isinstance(user_input.data, File)
        ]

        runner_packages: list[RunnerPackage] = []
        for testcase in self.testcases:
            assembled_program = assemble_program(testcase.run(user_input_step))

            # TEMP: For debugging purposes
            print(assembled_program)

            graph_files: list[File] = []
            for node in testcase.nodes:
                for output in node.outputs:
                    if isinstance(output.data, File):
                        graph_files.append(output.data)

            runner_package = RunnerPackage(
                entrypoint="__entrypoint.py",
                # TODO: instead of always passing in user_input, we can refactor in the future
                # to let ComputeGraph derive all the files needed to run the testcase
                files=[
                    *user_input_files,
                    *graph_files,
                    File(file_name="__entrypoint.py", content=assembled_program),
                ],
            )
            runner_packages.append(runner_package)

        runner_request = RunnerRequest.create(runner_packages, self.environment)
        task_publisher.publish(runner_request.model_dump_json(serialize_as_any=True))

        return TaskEvalResult(
            task_id=self.id, status=TaskEvalStatus.PENDING, result=runner_request.submission_id
        )

    def validate_user_input(self, user_input: Any) -> list[RequiredInput]:
        return RootModel[list[RequiredInput]].model_validate(user_input).root

    def validate_expected_answer(self, expected_answer: Any) -> list[ExpectedAnswer]:
        return RootModel[list[ExpectedAnswer]].model_validate(expected_answer).root
