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
from unicon_backend.evaluator.tasks.programming.steps import ComputeGraph
from unicon_backend.workers import task_publisher

logger = getLogger(__name__)


class Testcase(ComputeGraph):
    id: int


class ProgrammingTaskExpectedAnswer(BaseModel):
    testcase_id: int
    step_id: int
    expected_answer: Any


class ProgrammingTask(
    Task[list[File], dict[int, SubmissionId], list[ProgrammingTaskExpectedAnswer]]
):
    question: str
    environment: RunnerEnvironment
    templates: list[File]
    testcases: list[Testcase]

    runner: RunnerType = RunnerType.PODMAN

    def run(
        self,
        user_input: list[File],
        expected_answer: list[ProgrammingTaskExpectedAnswer],
    ) -> TaskEvalResult[dict[int, SubmissionId]]:
        # TODO: check if user input matches templates
        # TODO: user inputs can be a IMPLICIT input node for each test case
        #       this will help when it comes to passing user inputs to nodes in test case

        job_submissions: dict[int, SubmissionId] = {}
        for testcase in self.testcases:
            assembled_program = testcase.run()

            runner_request = RunnerRequest.create(
                entrypoint="__entrypoint.py",
                # TODO: instead of always passing in user_input, we can refactor in the future
                # to let ComputeGraph derive all the files needed to run the testcase
                files=[*user_input, File(file_name="__entrypoint.py", content=assembled_program)],
                environment=self.environment,
            )
            task_publisher.publish(runner_request.model_dump_json(serialize_as_any=True))

            job_submissions[testcase.id] = runner_request.submission_id

        return TaskEvalResult(
            task_id=self.id, status=TaskEvalStatus.PENDING, result=job_submissions
        )

    def validate_user_input(self, user_input: Any) -> list[File]:
        return RootModel[list[File]].model_validate(user_input).root

    def validate_expected_answer(self, expected_answer: Any) -> list[ProgrammingTaskExpectedAnswer]:
        return RootModel[list[ProgrammingTaskExpectedAnswer]].model_validate(expected_answer).root
