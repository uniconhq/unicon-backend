import json
import logging
from operator import attrgetter
from typing import TYPE_CHECKING, Any, cast

import pika
from pika.exchange_type import ExchangeType
from pika.spec import Basic
from sqlmodel import func, select

from unicon_backend.constants import EXCHANGE_NAME, RABBITMQ_URL, RESULT_QUEUE_NAME
from unicon_backend.database import SessionLocal
from unicon_backend.evaluator.tasks.programming.base import (
    ProgrammingTask,
    SocketResult,
    TaskEvalStatus,
    TestcaseResult,
)
from unicon_backend.lib.amqp import AsyncConsumer
from unicon_backend.models.problem import TaskResultORM
from unicon_backend.runner import JobResult, ProgramResult, Status

if TYPE_CHECKING:
    from unicon_backend.evaluator.tasks.programming.base import Testcase
    from unicon_backend.evaluator.tasks.programming.steps import OutputStep

logging.getLogger("pika").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class TaskResultsConsumer(AsyncConsumer):
    def __init__(self):
        super().__init__(RABBITMQ_URL, EXCHANGE_NAME, ExchangeType.topic, RESULT_QUEUE_NAME)

    def message_callback(
        self, _basic_deliver: Basic.Deliver, _properties: pika.BasicProperties, body: bytes
    ):
        response: JobResult = JobResult.model_validate_json(body)
        with SessionLocal() as db_session:
            task_result_db = db_session.scalar(
                select(TaskResultORM).where(TaskResultORM.job_id == response.id)
            )

            if task_result_db is None:
                # We have received a result a task that we are not aware of
                # TODO: We should either logged this somewhere or sent to a dead-letter exchange
                return

            task = cast(ProgrammingTask, task_result_db.task_attempt.task.to_task())
            testcases: list[Testcase] = sorted(task.testcases, key=attrgetter("id"))
            eval_results: list[ProgramResult] = sorted(response.results, key=attrgetter("id"))

            testcase_results: list[TestcaseResult] = []
            for testcase, eval_result in zip(testcases, eval_results, strict=False):
                output_step: OutputStep = testcase.output_step
                eval_value: dict[str, Any] = json.loads(eval_result.stdout)

                socket_results: list[SocketResult] = []
                for socket in output_step.data_in:
                    eval_socket_value = eval_value.get(socket.id, None)
                    # If there is no comparison required, the value is always regarded as correct
                    is_correct = (
                        socket.comparison.compare(eval_socket_value) if socket.comparison else True
                    )
                    socket_results.append(
                        SocketResult(id=socket.id, value=eval_socket_value, correct=is_correct)
                    )

                testcase_result = TestcaseResult(**eval_result.model_dump(), results=socket_results)
                testcase_result.status = (
                    Status.WA
                    if not all(socket_result.correct for socket_result in socket_results)
                    else testcase_result.status
                )
                testcase_results.append(testcase_result)

            task_result_db.status = TaskEvalStatus.SUCCESS
            task_result_db.completed_at = func.now()  # type: ignore
            task_result_db.result = [
                testcase_result.model_dump() for testcase_result in testcase_results
            ]

            db_session.add(task_result_db)
            db_session.commit()


task_results_consumer = TaskResultsConsumer()
