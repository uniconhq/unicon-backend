import logging
from http import HTTPStatus
from typing import Annotated
import pika

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from unicon_backend.dependencies.auth import get_current_user
from unicon_backend.dependencies.session import get_session
from unicon_backend.evaluator.contest import Definition, ExpectedAnswers, TaskResult, UserInputs
from unicon_backend.evaluator.tasks.base import TaskEvalStatus
from unicon_backend.helpers.constants import FRONTEND_URL
from unicon_backend.logger import setup_rich_logger
from unicon_backend.models import User
from unicon_backend.models.contest import (
    DefinitionORM,
    SubmissionORM,
    SubmissionStatus,
    TaskORM,
    TaskResultORM,
)
from unicon_backend.routers.auth import router as auth_router

logging.getLogger("passlib").setLevel(logging.ERROR)

app = FastAPI()
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


TASK_RUNNER_OUTPUT_QUEUE_NAME = "task_runner_results"


def listen_to_mq():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
    retrieve_channel = connection.channel()
    retrieve_channel.exchange_declare(
        exchange=TASK_RUNNER_OUTPUT_QUEUE_NAME, exchange_type="fanout"
    )
    result = retrieve_channel.queue_declare(queue="", exclusive=True)
    queue_name = result.method.queue
    retrieve_channel.queue_bind(exchange=TASK_RUNNER_OUTPUT_QUEUE_NAME, queue=queue_name)

    def callback(ch, method, properties, body):
        print(f" [x] {body}")

    retrieve_channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
    retrieve_channel.start_consuming()


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
) -> list[TaskResult]:
    definition_orm = session.scalar(
        select(DefinitionORM)
        .where(DefinitionORM.id == id)
        .options(selectinload(DefinitionORM.tasks))
    )

    if not definition_orm:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    def convert_orm_to_schemas(definiton_orm: DefinitionORM):
        value = {"name": definiton_orm.name, "description": definiton_orm.description, "tasks": []}
        for task_orm in definiton_orm.tasks:
            value["tasks"].append(
                {
                    "id": task_orm.id,
                    "type": task_orm.type,
                    "autograde": task_orm.autograde,
                    **task_orm.other_fields,
                }
            )
        definition = Definition.model_validate(value)
        return definition

    definition = convert_orm_to_schemas(definition_orm)

    result = definition.run(submission.user_inputs, submission.expected_answers)
    pending = any(task.result.status == TaskEvalStatus.PENDING for task in result)
    status = SubmissionStatus.Pending if pending else SubmissionStatus.Ok

    submission = SubmissionORM(definition_id=id, status=status, other_fields={})
    task_results = [
        TaskResultORM(
            other_fields=task.model_dump(serialize_as_any=True),
            submission_id=task.result if task.result.status == TaskEvalStatus.PENDING else None,
        )
        for task in result
    ]
    submission.task_results = task_results
    session.add(submission)
    session.commit()
    session.refresh(submission)
    return submission


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
