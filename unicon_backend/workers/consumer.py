import json
import logging

import pika
import sqlalchemy as sa
from pika.exchange_type import ExchangeType
from pika.spec import Basic

from unicon_backend.constants import EXCHANGE_NAME, RABBITMQ_URL, RESULT_QUEUE_NAME
from unicon_backend.database import SessionLocal
from unicon_backend.evaluator.tasks.base import TaskEvalStatus
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
        body_json: dict = json.loads(body)
        with SessionLocal() as session:
            task_result = session.scalar(
                sa.select(TaskResultORM).where(TaskResultORM.job_id == body_json["submission_id"])
            )
            if task_result is not None:
                task_result.status = TaskEvalStatus.SUCCESS
                task_result.result = body_json["result"]
                task_result.completed_at = sa.func.now()  # type: ignore

                session.add(task_result)
                session.commit()


task_results_consumer = TaskResultsConsumer()
