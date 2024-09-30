from http import HTTPStatus
import logging
from pprint import pprint
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from unicon_backend.dependencies.auth import get_current_user
from unicon_backend.dependencies.session import get_session
from unicon_backend.evaluator.contest import Definition, ExpectedAnswers, TaskResult, UserInputs
from unicon_backend.helpers.constants import FRONTEND_URL
from unicon_backend.logger import setup_rich_logger
from unicon_backend.models import User
from unicon_backend.models.contest import DefinitionORM, TaskORM
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
    # definition: Definition
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
) -> list[TaskResult]:
    # Retrieve defintion from db
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

    return definition.run(submission.user_inputs, submission.expected_answers)
