import asyncio
import json
import logging
from http import HTTPStatus
from typing import Annotated

import aio_pika
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from unicon_backend.constants import FRONTEND_URL, sql_engine
from unicon_backend.dependencies.auth import get_current_user
from unicon_backend.dependencies.session import get_session
from unicon_backend.evaluator.contest import Definition, ExpectedAnswers, UserInputs
from unicon_backend.evaluator.tasks.base import TaskEvalStatus
from unicon_backend.logger import setup_rich_logger
from unicon_backend.models import (
    DefinitionORM,
    SubmissionORM,
    SubmissionStatus,
    TaskORM,
    TaskResultORM,
    User,
)
from unicon_backend.routers.auth import router as auth_router

logging.getLogger("passlib").setLevel(logging.ERROR)

TASK_RUNNER_OUTPUT_QUEUE_NAME = "task_runner_results"


async def listen_to_mq():
    print("CALLED")
    connection = await aio_pika.connect_robust("amqp://localhost/")

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
                    submission = session.scalar(
                        select(TaskResultORM).where(
                            TaskResultORM.task_submission_id == body["submission_id"]
                        )
                    )
                    if not submission:
                        return
                    submission.other_fields = body["result"]
                    session.add(submission)
                    session.commit()

        await queue.consume(callback)

        await asyncio.Future()


def lifespan(app: FastAPI):
    asyncio.create_task(listen_to_mq())
    yield


app = FastAPI(lifespan=lifespan)
setup_rich_logger()

origins = [FRONTEND_URL]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

# TODO: these routes are to demonstrate authentication. Remove once we actually have other content.


@app.get("/noauth")
def no_auth():
    return "success"


@app.get("/auth")
def auth(user: Annotated[User, Depends(get_current_user)]):
    return f"success, hi {user.username}"


class Submission(BaseModel):
    # TODO: tie expected_answers to task model
    expected_answers: ExpectedAnswers
    user_inputs: UserInputs


@app.post("/definitions")
def submit_definition(
    definition: Definition,
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
):
    definition_orm = DefinitionORM(name=definition.name, description=definition.description)

    def convert_task_to_orm(id, type, autograde, **other_fields):
        return TaskORM(id=id, type=type, autograde=autograde, other_fields=other_fields)

    for task in definition.tasks:
        task_orm = convert_task_to_orm(**task.model_dump(serialize_as_any=True))
        definition_orm.tasks.append(task_orm)

    session.add(definition_orm)
    session.commit()
    session.refresh(definition_orm)
    return definition_orm


@app.post("/definitions/{id}/submission")
def submit(
    id: int,
    submission: Submission,
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[TaskResultORM]:
    definition_orm = session.scalar(
        select(DefinitionORM)
        .where(DefinitionORM.id == id)
        .options(selectinload(DefinitionORM.tasks))
    )

    if not definition_orm:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    def convert_orm_to_schemas(definiton_orm: DefinitionORM):
        tasks: list[dict] = [
            {
                "id": task_orm.id,
                "type": task_orm.type,
                "autograde": task_orm.autograde,
                **task_orm.other_fields,
            }
            for task_orm in definiton_orm.tasks
        ]

        return Definition.model_validate(
            {"name": definiton_orm.name, "description": definiton_orm.description, "tasks": tasks}
        )

    definition = convert_orm_to_schemas(definition_orm)

    result = definition.run(submission.user_inputs, submission.expected_answers)
    pending = any(task.result.status == TaskEvalStatus.PENDING for task in result)
    status = SubmissionStatus.Pending if pending else SubmissionStatus.Ok

    submission_orm = SubmissionORM(definition_id=id, status=status, other_fields={})
    task_results = [
        TaskResultORM(
            other_fields=task.model_dump(mode="json"),
            task_submission_id=task.result.result
            if task.result.status == TaskEvalStatus.PENDING
            else None,
        )
        for task in result
    ]
    submission_orm.task_results = task_results
    session.add(submission)
    session.commit()
    session.refresh(submission)
    return submission_orm.task_results


@app.get("/submission/{id}")
def get_submission(
    id: int,
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
):
    submission = session.scalar(
        select(SubmissionORM)
        .where(SubmissionORM.id == id)
        .options(selectinload(SubmissionORM.task_results))
    )

    return submission
