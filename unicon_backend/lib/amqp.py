import abc
from asyncio import AbstractEventLoop
from logging import getLogger

import pika  # type: ignore
from pika.adapters.asyncio_connection import AsyncioConnection  # type: ignore
from pika.channel import Channel  # type: ignore
from pika.exchange_type import ExchangeType  # type: ignore
from pika.frame import Method  # type: ignore
from pika.spec import Basic, BasicProperties  # type: ignore

logger = getLogger(__name__)


# Reference: https://github.com/pika/pika/blob/main/examples/asynchronous_consumer_example.py
class AsyncConsumer(abc.ABC):
    def __init__(
        self,
        amqp_url: str,
        exchange_name: str,
        exchange_type: ExchangeType,
        queue_name: str,
        routing_key: str | None = None,
    ):
        self.exchange_name = exchange_name
        self.exchange_type = exchange_type

        self.queue_name = queue_name
        # NOTE: If routing_key is not provided, it will default to the queue_name
        self.routing_key = routing_key or queue_name

        self._url = amqp_url

        # NOTE: These will be set when the connection is established
        self._connection: AsyncioConnection | None = None
        self._channel: Channel | None = None
        self._consumer_tag: str | None = None

        self._closing = False
        self._consuming = False

    def close_connection(self):
        self._consuming = False
        if not (self._connection.is_closing or self._connection.is_closed):
            self._connection.close()

    def on_connection_open(self, _connection: AsyncioConnection):
        self.open_channel()

    def on_connection_open_error(self, _connection: AsyncioConnection, error: Exception):
        logger.error(f"Connection open error: {error}")

    def on_connection_closed(self, _connection: AsyncioConnection, reason: Exception):
        self._channel = None
        if not self._closing:
            # If connection was closed unexpectedly
            logger.error(f"Connection closed unexpectedly: {reason}")

    def open_channel(self):
        assert self._connection is not None
        self._connection.channel(on_open_callback=self.on_channel_open)

    def on_channel_open(self, channel: Channel):
        self._channel = channel

        self._channel.add_on_close_callback(self.on_channel_closed)
        self.setup_exchange()

    def on_channel_closed(self, _channel: Channel, _reason: Exception):
        self.close_connection()

    def setup_exchange(self):
        self._channel.exchange_declare(
            exchange=self.exchange_name,
            exchange_type=self.exchange_type,
            callback=self.on_exchange_declare_ok,
        )

    def on_exchange_declare_ok(self, _frame: Method):
        self.setup_queue()

    def setup_queue(self):
        # TODO: Hardcoded for the queue to be durable. This should be configurable
        self._channel.queue_declare(
            queue=self.queue_name, callback=self.on_queue_declare_ok, durable=True
        )

    def on_queue_declare_ok(self, _frame: Method):
        assert self._channel is not None
        self._channel.queue_bind(
            self.queue_name, self.exchange_name, self.routing_key, callback=self.on_bind_ok
        )

    def on_bind_ok(self, _frame: Method):
        self.set_qos()

    def set_qos(self):
        assert self._channel is not None
        self._channel.basic_qos(prefetch_count=1, callback=self.on_basic_qos_ok)

    def on_basic_qos_ok(self, _frame: Method):
        self.start_consuming()

    def start_consuming(self):
        assert self._channel is not None
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)
        self._consumer_tag = self._channel.basic_consume(self.queue_name, self.on_message)
        self._consuming = True

    def on_consumer_cancelled(self, _frame: Method):
        self._channel and self._channel.close()

    def on_message(
        self,
        _channel: Channel,
        basic_deliver: Basic.Deliver,
        properties: BasicProperties,
        body: bytes,
    ):
        assert self._channel is not None
        self.message_callback(basic_deliver, properties, body)
        self._channel.basic_ack(basic_deliver.delivery_tag)

    def stop_consuming(self):
        if self._channel:
            self._channel.basic_cancel(self._consumer_tag, callback=self.on_cancel_ok)

    def on_cancel_ok(self, _frame: Method):
        assert self._channel is not None
        self._consuming = False
        self._channel.close()

    @abc.abstractmethod
    def message_callback(
        self, basic_deliver: Basic.Deliver, properties: BasicProperties, body: bytes
    ): ...

    def run(self, event_loop: AbstractEventLoop | None = None):
        self._connection = AsyncioConnection(
            parameters=pika.URLParameters(self._url),
            on_open_callback=self.on_connection_open,
            on_open_error_callback=self.on_connection_open_error,
            on_close_callback=self.on_connection_closed,
            custom_ioloop=event_loop,
        )

    def stop(self):
        if not self._closing:
            self._closing = True
            self._consuming and self.stop_consuming()
