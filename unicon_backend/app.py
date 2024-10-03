import asyncio
import json
import logging

import aio_pika
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from unicon_backend.constants import FRONTEND_URL, RABBITMQ_URL, sql_engine
from unicon_backend.evaluator.tasks.base import TaskEvalStatus
from unicon_backend.logger import setup_rich_logger
from unicon_backend.models import TaskResultORM
from unicon_backend.routers import auth, contest

logging.getLogger("passlib").setLevel(logging.ERROR)

TASK_RUNNER_OUTPUT_QUEUE_NAME = "task_runner_results"


async def listen_to_mq():
    connection = await aio_pika.connect_robust(RABBITMQ_URL)

    async with connection:
        retrieve_channel = await connection.channel()
        exchange = await retrieve_channel.declare_exchange(
            TASK_RUNNER_OUTPUT_QUEUE_NAME, type="fanout"
        )

        queue = await retrieve_channel.declare_queue(exclusive=True)
        # queue_name = result.method.queue

        await queue.bind(exchange)
        # await retrieve_channel.queue_bind(exchange=TASK_RUNNER_OUTPUT_QUEUE_NAME, queue=queue_name)

        async def callback(message: aio_pika.IncomingMessage):
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

        await queue.consume(callback)

        await asyncio.Future()


def lifespan(app: FastAPI):
    asyncio.create_task(listen_to_mq())
    yield


app = FastAPI(lifespan=lifespan)
setup_rich_logger()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(contest.router)
