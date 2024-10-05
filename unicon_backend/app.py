import asyncio
import json
import logging
from contextlib import asynccontextmanager

import pika  # type: ignore
import pika.exchange_type  # type: ignore
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pika.spec import Basic  # type: ignore
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


class TaskResultsConsumer(AsyncConsumer):
    def __init__(self):
        super().__init__(
            RABBITMQ_URL,
            RESULT_QUEUE_NAME,
            pika.exchange_type.ExchangeType.direct,
            RESULT_QUEUE_NAME,
            RESULT_QUEUE_NAME,
        )

    def message_callback(
        self, _basic_deliver: Basic.Deliver, _properties: pika.BasicProperties, body: bytes
    ):
        body_json: dict = json.loads(body)
        with Session(sql_engine) as session:
            task_result = session.scalar(
                select(TaskResultORM).where(TaskResultORM.job_id == body_json["submission_id"])
            )
            if task_result is not None:
                task_result.status = TaskEvalStatus.SUCCESS
                task_result.result = body_json["result"]

                session.add(task_result)
                session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task_results_consumer = TaskResultsConsumer()
    # NOTE: At this point, the event loop is already running because FastAPI has started the server
    task_results_consumer.run(event_loop=asyncio.get_event_loop())
    yield
    task_results_consumer.stop()


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
