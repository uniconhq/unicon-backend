import abc
from asyncio import AbstractEventLoop
from logging import getLogger
from typing import Literal

import pika
from pika.adapters.asyncio_connection import AsyncioConnection
from pika.channel import Channel
from pika.exchange_type import ExchangeType
from pika.frame import Method
from pika.spec import Basic, BasicProperties

logger = getLogger(__name__)


# Reference: https://github.com/pika/pika/blob/main/examples/asynchronous_consumer_example.py
class AsyncConsumer(abc.ABC):
    def __init__(
        self,
        amqp_url: str,
        exchange_name: str,
        exchange_type: ExchangeType,
        queue_name: str,
        connection_name: str,
        routing_key: str | None = None,
    ):
        self.exchange_name = exchange_name
        self.exchange_type = exchange_type

        self.queue_name = queue_name
        # NOTE: If routing_key is not provided, it will default to the queue_name
        self.routing_key = routing_key or queue_name

        self.conn_name = connection_name

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

    def on_connection_open_error(self, _connection: AsyncioConnection, error: BaseException):
        logger.error(f"Connection open error: {error}")

    def on_connection_closed(self, _connection: AsyncioConnection, reason: BaseException):
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
        assert self._channel
        self._channel.close()

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
        conn_params = pika.URLParameters(self._url)
        conn_params.client_properties = {"connection_name": self.conn_name}
        self._connection = AsyncioConnection(
            parameters=conn_params,
            on_open_callback=self.on_connection_open,
            on_open_error_callback=self.on_connection_open_error,
            on_close_callback=self.on_connection_closed,
            custom_ioloop=event_loop,
        )

    def stop(self):
        if not self._closing:
            self._closing = True
            self._consuming and self.stop_consuming()


class AsyncPublisher(abc.ABC):
    def __init__(
        self,
        amqp_url: str,
        exchange_name: str,
        exchange_type: ExchangeType,
        queue_name: str,
        connection_name: str,
        routing_key: str | None = None,
    ):
        self.exchange_name = exchange_name
        self.exchange_type = exchange_type

        self.queue_name = queue_name
        # NOTE: If routing_key is not provided, it will default to the queue_name
        self.routing_key = routing_key or queue_name

        self.conn_name = connection_name

        self._url = amqp_url

        self._connection: AsyncioConnection | None = None
        self._channel: Channel | None = None

        self._deliveries: dict[int, Literal[True]] = {}
        self._acked: int = 0  # Number of messages acknowledged
        self._nacked: int = 0  # Number of messages rejected
        self._message_number: int = 0  # Number of messages published

        self._closing = False

    def on_connection_open(self, _connection: AsyncioConnection):
        assert self._connection is not None
        self._connection.channel(on_open_callback=self.on_channel_open)

    def on_connection_open_error(self, _connection: AsyncioConnection, err: BaseException) -> None:
        logger.error(f"Connection open error: {err}")

    def on_connection_closed(self, _unused_connection, reason):
        self._channel = None
        if not self._closing:
            logger.warning(f"Connection closed unexpectedly: {reason}")

    def on_channel_open(self, channel: Channel):
        self._channel = channel
        self._channel.add_on_close_callback(self.on_channel_closed)
        self.setup_exchange(self.exchange_name)

    def on_channel_closed(self, channel: Channel, reason):
        self._channel = None
        if not self._closing:
            assert self._connection is not None
            self._connection.close()

    def setup_exchange(self, exchange_name):
        self._channel.exchange_declare(
            exchange=exchange_name,
            exchange_type=self.exchange_type,
            callback=self.on_exchange_declareok,
        )

    def on_exchange_declareok(self, _frame: Method):
        assert self._channel is not None
        # TODO: Hardcoded for the queue to be durable. This should be configurable
        self._channel.queue_declare(
            queue=self.queue_name, callback=self.on_queue_declareok, durable=True
        )

    def on_queue_declareok(self, _frame: Method):
        assert self._channel is not None
        self._channel.queue_bind(
            self.queue_name,
            self.exchange_name,
            routing_key=self.routing_key,
            callback=self.start_publishing,
        )

    def start_publishing(self, _frame: Method):
        assert self._channel is not None
        self._channel.confirm_delivery(self.on_delivery_confirmation)

    def on_delivery_confirmation(self, frame: Method):
        confirmation_type = frame.method.NAME.split(".")[1].lower()
        ack_multiple = frame.method.multiple
        delivery_tag = frame.method.delivery_tag

        self._acked += confirmation_type == "ack"
        self._nacked += confirmation_type == "nack"

        del self._deliveries[delivery_tag]

        if ack_multiple:
            for tmp_tag in filter(lambda tmp_tag: tmp_tag <= delivery_tag, self._deliveries):
                self._acked += 1
                del self._deliveries[tmp_tag]

    @abc.abstractmethod
    def publish(self, payload: str, content_type: str): ...

    def run(self, event_loop: AbstractEventLoop | None = None):
        self._connection = None

        self._deliveries.clear()
        self._acked = 0
        self._nacked = 0
        self._message_number = 0

        conn_params = pika.URLParameters(self._url)
        conn_params.client_properties = {"connection_name": self.conn_name}
        self._connection = AsyncioConnection(
            parameters=conn_params,
            on_open_callback=self.on_connection_open,
            on_open_error_callback=self.on_connection_open_error,
            on_close_callback=self.on_connection_closed,
            custom_ioloop=event_loop,
        )

    def stop(self):
        self._closing = True

        if self._channel is not None:
            self._channel.close()

        if self._connection is not None:
            self._connection.close()
