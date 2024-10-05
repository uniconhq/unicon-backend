import asyncio
import json
import logging
from contextlib import asynccontextmanager

import aio_pika
import pika  # type: ignore
import pika.exchange_type  # type: ignore
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from unicon_backend.constants import FRONTEND_URL, RABBITMQ_URL, RESULT_QUEUE_NAME, sql_engine
from unicon_backend.evaluator.tasks.base import TaskEvalStatus
from unicon_backend.lib.amqp import AsyncConsumer
from unicon_backend.logger import setup_rich_logger
from unicon_backend.models import TaskResultORM
from unicon_backend.routers import auth, contest

logging.getLogger("passlib").setLevel(logging.ERROR)
setup_rich_logger()


async def listen_to_mq():
    connection = await aio_pika.connect_robust(RABBITMQ_URL)

    async with connection:
        retrieve_channel = await connection.channel()
        result_queue = await retrieve_channel.declare_queue(RESULT_QUEUE_NAME, durable=True)

        async def on_task_complete(message: aio_pika.IncomingMessage):
            async with message.process():
                body = json.loads(message.body)
                with Session(sql_engine) as session:
                    if (
                        task_result := session.scalar(
                            select(TaskResultORM).where(
                                TaskResultORM.job_id == body["submission_id"]
                            )
                        )
                    ) is not None:
                        task_result.status = TaskEvalStatus.SUCCESS
                        task_result.result = body["result"]

                        session.add(task_result)
                        session.commit()

        await result_queue.consume(on_task_complete)
        await asyncio.Future()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # NOTE: Does not actually run processes the message, just listens and prints it to stdout
    msg_consumer = AsyncConsumer(
        RABBITMQ_URL,
        RESULT_QUEUE_NAME,
        pika.exchange_type.ExchangeType.direct,
        RESULT_QUEUE_NAME,
        RESULT_QUEUE_NAME,
    )
    # NOTE: At this point, the event loop is already running because FastAPI has started the server
    msg_consumer.run(event_loop=asyncio.get_event_loop())
    yield
    msg_consumer.stop()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(contest.router)
