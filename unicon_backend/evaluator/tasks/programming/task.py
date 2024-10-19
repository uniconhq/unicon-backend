from logging import getLogger
from typing import Any

from pydantic import BaseModel, RootModel

from unicon_backend.evaluator.tasks import Task, TaskEvalResult, TaskEvalStatus
from unicon_backend.evaluator.tasks.programming.artifact import File
from unicon_backend.evaluator.tasks.programming.runner import (
    RunnerEnvironment,
    RunnerRequest,
    RunnerType,
    SubmissionId,
)
from unicon_backend.evaluator.tasks.programming.steps import (
    ComputeGraph,
    InputStep,
    StepSocket,
    StepType,
)
from unicon_backend.workers import task_publisher

logger = getLogger(__name__)

USER_INPUT_STEP_ID: int = 0


class Testcase(ComputeGraph):
    id: int


class RequiredInput(BaseModel):
    id: int
    data: File


class ExpectedAnswer(BaseModel):
    testcase_id: int
    step_id: int
    expected_answer: Any


class ProgrammingTask(Task[list[RequiredInput], dict[int, SubmissionId], list[ExpectedAnswer]]):
    question: str
    environment: RunnerEnvironment
    required_inputs: list[RequiredInput]
    testcases: list[Testcase]

    runner: RunnerType = RunnerType.PODMAN

    def run(self, user_inputs: list[RequiredInput], _) -> TaskEvalResult[dict[int, SubmissionId]]:
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
                StepSocket(id=user_input.id, data=user_input.data, name=f"USER_INPUT_{idx}")
                for idx, user_input in enumerate(user_inputs)
            ],
            type=StepType.INPUT,
        )
        user_input_files = [user_input.data for user_input in user_inputs]

        job_submissions: dict[int, SubmissionId] = {}
        for testcase in self.testcases:
            assembled_program = testcase.run(user_input_step)

            # TEMP: For debugging purposes
            print(assembled_program)

            runner_request = RunnerRequest.create(
                entrypoint="__entrypoint.py",
                # TODO: instead of always passing in user_input, we can refactor in the future
                # to let ComputeGraph derive all the files needed to run the testcase
                files=[
                    *user_input_files,
                    File(file_name="__entrypoint.py", content=assembled_program),
                ],
                environment=self.environment,
            )
            task_publisher.publish(runner_request.model_dump_json(serialize_as_any=True))

            job_submissions[testcase.id] = runner_request.submission_id

        return TaskEvalResult(
            task_id=self.id, status=TaskEvalStatus.PENDING, result=job_submissions
        )

    def validate_user_input(self, user_input: Any) -> list[RequiredInput]:
        return RootModel[list[RequiredInput]].model_validate(user_input).root

    def validate_expected_answer(self, expected_answer: Any) -> list[ExpectedAnswer]:
        return RootModel[list[ExpectedAnswer]].model_validate(expected_answer).root
