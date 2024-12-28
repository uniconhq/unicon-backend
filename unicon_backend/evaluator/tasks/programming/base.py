from functools import cached_property
from logging import getLogger
from typing import Any, Literal, Self, cast

from pydantic import BaseModel, RootModel, model_validator

from unicon_backend.evaluator.tasks import Task, TaskEvalResult, TaskEvalStatus, TaskType
from unicon_backend.evaluator.tasks.programming.artifact import File, PrimitiveData
from unicon_backend.evaluator.tasks.programming.security import mpi_sandbox
from unicon_backend.evaluator.tasks.programming.steps import (
    ComputeGraph,
    InputStep,
    OutputStep,
    StepSocket,
    StepType,
)
from unicon_backend.lib.common import CustomSQLModel
from unicon_backend.runner import ComputeContext, JobId, ProgramResult, RunnerJob, RunnerProgram
from unicon_backend.workers.publisher import task_publisher

logger = getLogger(__name__)

USER_INPUT_STEP_ID: int = 0


class Testcase(ComputeGraph):
    id: int

    @model_validator(mode="after")
    def check_exactly_one_output_step(self) -> Self:
        num_output_steps: int = len([node for node in self.nodes if node.type == StepType.OUTPUT])
        if num_output_steps != 1:
            raise ValueError(f"Expected exactly 1 output step, found {num_output_steps}")
        return self

    @cached_property
    def output_step(self) -> OutputStep:
        return cast(OutputStep, next(node for node in self.nodes if node.type == StepType.OUTPUT))


class SocketResult(CustomSQLModel):
    """
    This class is used to store whether the result of an output socket is right or wrong.
    Note that whether or not to show this information (public) and other variables should be derived from data in Testcase.
    """

    id: str
    value: Any
    correct: bool


class TestcaseResult(ProgramResult):
    results: list[SocketResult] | None = None


class RequiredInput(BaseModel):
    id: str
    data: PrimitiveData | File


class ProgrammingTask(Task[list[RequiredInput], JobId]):
    type: Literal[TaskType.PROGRAMMING]
    question: str
    environment: ComputeContext
    required_inputs: list[RequiredInput]
    testcases: list[Testcase]

    def create_input_step(self, user_inputs: list[RequiredInput]) -> InputStep:
        """
        Transform user input into InputStep
        This is so that we simply treat it as a node in the graph
        NOTE: We assume that the id of user inputs is always 0
        """
        return InputStep(
            id=USER_INPUT_STEP_ID,
            inputs=[],
            outputs=[
                StepSocket(id=str(user_input.id), data=user_input.data)
                for user_input in user_inputs
            ],
            type=StepType.INPUT,
        )

    def _get_runner_programs(self, user_inputs: list[RequiredInput]) -> list[RunnerProgram]:
        runner_programs: list[RunnerProgram] = []
        for testcase in self.testcases:
            assembled_program = mpi_sandbox(testcase.run(self.create_input_step(user_inputs)))

            logger.debug(f"Assembled Program:\n{assembled_program}")

            graph_files: list[File] = []
            for node in filter(lambda node: node.type == StepType.INPUT, testcase.nodes):
                graph_files.extend(
                    output.data for output in node.outputs if isinstance(output.data, File)
                )

            runner_programs.append(
                RunnerProgram(
                    id=testcase.id,
                    entrypoint="__entrypoint.py",
                    # TODO: instead of always passing in user_input, we can refactor in the future
                    # to let ComputeGraph derive all the files needed to run the testcase
                    files=[
                        *graph_files,
                        File(name="__entrypoint.py", content=assembled_program.code),
                    ],
                )
            )
        return runner_programs

    def run(self, user_inputs: list[RequiredInput]) -> TaskEvalResult[JobId]:
        # Check if all required inputs are provided
        for required_input in self.required_inputs:
            if not any(required_input.id == user_input.id for user_input in user_inputs):
                raise ValueError(f"Required input {required_input.id} not provided")

        runner_programs = self._get_runner_programs(user_inputs)

        runner_job = RunnerJob.create(runner_programs, self.environment)
        task_publisher.publish(runner_job.model_dump_json(serialize_as_any=True))

        return TaskEvalResult(task_id=self.id, status=TaskEvalStatus.PENDING, result=runner_job.id)

    def validate_user_input(self, user_input: Any) -> list[RequiredInput]:
        return RootModel[list[RequiredInput]].model_validate(user_input).root
