import logging

from pika import BasicProperties, DeliveryMode
from pika.exchange_type import ExchangeType

from unicon_backend.constants import (
    AMQP_CONN_NAME,
    AMQP_EXCHANGE_NAME,
    AMQP_TASK_QUEUE_NAME,
    AMQP_URL,
)
from unicon_backend.lib.amqp import AsyncPublisher

logger = logging.getLogger(__name__)


class TaskPublisher(AsyncPublisher):
    def __init__(self):
        super().__init__(
            AMQP_URL,
            AMQP_EXCHANGE_NAME,
            ExchangeType.topic,
            AMQP_TASK_QUEUE_NAME,
            f"{AMQP_CONN_NAME}::publisher",
        )

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
