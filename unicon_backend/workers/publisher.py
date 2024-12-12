import logging

from pika import BasicProperties, DeliveryMode
from pika.exchange_type import ExchangeType

from unicon_backend.constants import EXCHANGE_NAME, RABBITMQ_URL, TASK_QUEUE_NAME
from unicon_backend.lib.amqp import AsyncPublisher

logging.getLogger("pika").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class TaskPublisher(AsyncPublisher):
    def __init__(self):
        super().__init__(RABBITMQ_URL, EXCHANGE_NAME, ExchangeType.topic, TASK_QUEUE_NAME)

    def publish(self, payload: str, content_type: str = "application/json"):
        assert self._channel is not None

        self._channel.basic_publish(
            self.exchange_name,
            self.routing_key,
            payload,
            properties=BasicProperties(
                content_type=content_type, delivery_mode=DeliveryMode.Persistent
            ),
        )

        # Mark that the message was published for delivery confirmation
        self._message_number += 1
        self._deliveries[self._message_number] = True


task_publisher = TaskPublisher()
