import logging

import pika
import sqlalchemy as sa
from pika.exchange_type import ExchangeType
from pika.spec import Basic
from sqlmodel import select

from unicon_backend.constants import EXCHANGE_NAME, RABBITMQ_URL, RESULT_QUEUE_NAME
from unicon_backend.database import SessionLocal
from unicon_backend.evaluator.tasks.base import TaskEvalStatus
from unicon_backend.lib.amqp import AsyncConsumer
from unicon_backend.models.problem import TaskResultORM
from unicon_backend.runner import JobResult

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
            task_result = db_session.scalar(
                select(TaskResultORM).where(TaskResultORM.job_id == str(response.id))
            )
            if task_result is not None:
                task_result.status = TaskEvalStatus.SUCCESS
                task_result.result = response.model_dump(mode="json")  # TEMP
                task_result.completed_at = sa.func.now()  # type: ignore

                db_session.add(task_result)
                db_session.commit()


task_results_consumer = TaskResultsConsumer()
