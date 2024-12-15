import json
import logging
from typing import cast

import pika
import sqlalchemy as sa
from pika.exchange_type import ExchangeType
from pika.spec import Basic
from sqlmodel import col

from unicon_backend.constants import EXCHANGE_NAME, RABBITMQ_URL, RESULT_QUEUE_NAME
from unicon_backend.database import SessionLocal
from unicon_backend.evaluator.tasks.base import TaskEvalStatus
from unicon_backend.evaluator.tasks.programming.runner import RunnerResponse, Status
from unicon_backend.evaluator.tasks.programming.steps import (
    OutputStep,
    ProcessedResult,
    SocketResult,
    StepType,
)
from unicon_backend.evaluator.tasks.programming.task import ProgrammingTask
from unicon_backend.lib.amqp import AsyncConsumer
from unicon_backend.models.problem import TaskResultORM

logging.getLogger("pika").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class TaskResultsConsumer(AsyncConsumer):
    def __init__(self):
        super().__init__(RABBITMQ_URL, EXCHANGE_NAME, ExchangeType.topic, RESULT_QUEUE_NAME)

    def message_callback(
        self, _basic_deliver: Basic.Deliver, _properties: pika.BasicProperties, body: bytes
    ):
        body_json: RunnerResponse = RunnerResponse.model_validate_json(body)
        with SessionLocal() as session:
            task_result = session.scalar(
                sa.select(TaskResultORM).where(col(TaskResultORM.job_id) == body_json.submission_id)
            )
            if task_result is not None:
                task_result.status = TaskEvalStatus.SUCCESS
                task_result.completed_at = sa.func.now()  # type: ignore

                # Evaluate result based on OutputStep
                task = cast(ProgrammingTask, task_result.task_attempt.task.to_task())

                # Assumption: testcase index = result index
                # Updates to testcases must be done very carefully because of this assumption.
                # To remove this assumption, we need to add a testcase_id field to the result model.
                processedResults: list[ProcessedResult] = []
                for testcase in task.testcases:
                    result = [
                        testcaseResult
                        for testcaseResult in body_json.result
                        if testcaseResult.id == testcase.id
                    ][0]

                    output_step = OutputStep.model_validate(
                        [node for node in testcase.nodes if node.type == StepType.OUTPUT][0],
                        from_attributes=True,
                    )
                    actual_output = json.loads(result.stdout)

                    socket_results: list[SocketResult] = []
                    for config in output_step.socket_metadata:
                        socket_result = SocketResult(
                            id=config.id, value=actual_output.get(config.id, None), correct=True
                        )
                        if config.comparison is not None:
                            socket_result.correct = config.comparison.compare(socket_result.value)

                        if not socket_result.correct and result.status == Status.OK:
                            result.status = Status.WA

                        socket_results.append(socket_result)

                    processedResults.append(
                        ProcessedResult.model_validate(
                            {**result.model_dump(), "results": socket_results}
                        )
                    )

                task_result.result = [result.model_dump() for result in processedResults]

                session.add(task_result)
                session.commit()


task_results_consumer = TaskResultsConsumer()
