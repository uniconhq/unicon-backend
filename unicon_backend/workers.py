import json
from logging import getLogger

import pika  # type: ignore
import sqlalchemy as sa
from pika import BasicProperties, DeliveryMode  # type: ignore
from pika.channel import Channel  # type: ignore
from pika.exchange_type import ExchangeType  # type: ignore
from pika.spec import Basic  # type: ignore

from unicon_backend.constants import EXCHANGE_NAME, RABBITMQ_URL, RESULT_QUEUE_NAME, TASK_QUEUE_NAME
from unicon_backend.database import SessionLocal
from unicon_backend.evaluator.tasks import TaskEvalStatus
from unicon_backend.lib.amqp import AsyncConsumer
from unicon_backend.models import TaskResultORM

logger = getLogger(__name__)


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
                task_result.completed_at = sa.func.now()
                task_result.result = body_json["result"]

                session.add(task_result)
                session.commit()


class TaskPublisher:
    def __init__(self) -> None:
        self._connection: pika.BlockingConnection | None = None
        self._channel: Channel | None = None

    def publish(self, payload: str, content_type: str = "application/json"):
        assert self._channel is not None
        self._channel.basic_publish(
            EXCHANGE_NAME,
            TASK_QUEUE_NAME,
            payload,
            properties=BasicProperties(
                content_type=content_type, delivery_mode=DeliveryMode.Persistent
            ),
        )

    def run(self):
        self._connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        self._channel = self._connection.channel()

        self._channel.queue_declare(queue=TASK_QUEUE_NAME, durable=True)
        self._channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type=ExchangeType.topic)
        self._channel.queue_bind(
            exchange=EXCHANGE_NAME, queue=TASK_QUEUE_NAME, routing_key=TASK_QUEUE_NAME
        )
        self._channel.confirm_delivery()

    def stop(self):
        assert self._channel is not None
        assert self._connection is not None

        self._channel.close()
        self._connection.close()


task_results_consumer = TaskResultsConsumer()
task_publisher = TaskPublisher()
