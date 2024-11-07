from http import HTTPStatus
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from unicon_backend.dependencies import get_current_user, get_db_session
from unicon_backend.evaluator.contest import Definition, ExpectedAnswers, UserInputs
from unicon_backend.evaluator.tasks.base import TaskEvalResult, TaskEvalStatus
from unicon_backend.models import (
    DefinitionORM,
    SubmissionORM,
    SubmissionStatus,
    TaskORM,
    TaskResultORM,
)
from unicon_backend.schemas.contest import BaseDefinitionDTO

router = APIRouter(prefix="/contests", tags=["contest"], dependencies=[Depends(get_current_user)])


@router.get("/definitions", summary="Get all definitions")
def get_definitions(
    db_session: Annotated[Session, Depends(get_db_session)],
) -> list[BaseDefinitionDTO]:
    definitions = db_session.scalars(sa.select(DefinitionORM))
    return definitions


# TEMPORARY
# TODO: Remove this once we have a proper way of converting ORM to Pydantic models
class PydanticDefinitionORM(BaseModel):
    id: int
    name: str
    description: str


@router.post("/definitions", summary="Submit a contest definition")
def submit_definition(
    definition: Definition,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> DefinitionORM:
    definition_orm = DefinitionORM(name=definition.name, description=definition.description)

    def convert_task_to_orm(id, type, autograde, **other_fields):
        return TaskORM(id=id, type=type, autograde=autograde, other_fields=other_fields)

    for task in definition.tasks:
        task_orm = convert_task_to_orm(**task.model_dump(serialize_as_any=True))
        definition_orm.tasks.append(task_orm)

    db_session.add(definition_orm)
    db_session.commit()
    db_session.refresh(definition_orm)
    return definition_orm


@router.patch("/definitions/{id}", summary="Update a contest definition")
def update_definition(
    id: int, definition: Definition, db_session: Annotated[Session, Depends(get_db_session)]
):
    definition_orm = db_session.scalar(
        sa.select(DefinitionORM)
        .where(DefinitionORM.id == id)
        .options(selectinload(DefinitionORM.tasks))
    )

    if definition_orm is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Contest definition not found")

    # Delete existing tasks and add new ones
    for task_orm in definition_orm.tasks:
        db_session.delete(task_orm)

    def convert_task_to_orm(id, type, autograde, **other_fields):
        return TaskORM(id=id, type=type, autograde=autograde, other_fields=other_fields)

    for task in definition.tasks:
        task_orm = convert_task_to_orm(**task.model_dump(serialize_as_any=True))
        definition_orm.tasks.append(task_orm)

    db_session.add(definition_orm)
    db_session.commit()
    db_session.refresh(definition_orm)

    return definition_orm


class ContestSubmission(BaseModel):
    expected_answers: ExpectedAnswers
    user_inputs: UserInputs


@router.post(
    "/definitions/{id}/submissions", summary="Upload a submission for a contest definition"
)
def submit_contest_submission(
    id: int,
    submission: ContestSubmission,
    db_session: Annotated[Session, Depends(get_db_session)],
    task_id: int | None = None,
):
    definition_orm = db_session.scalar(
        sa.select(DefinitionORM)
        .where(DefinitionORM.id == id)
        .options(selectinload(DefinitionORM.tasks))
    )

    if definition_orm is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Contest definition not found")

    definition: Definition = Definition.model_validate(
        {
            "name": definition_orm.name,
            "description": definition_orm.description,
            "tasks": [
                {
                    "id": task_orm.id,
                    "type": task_orm.type,
                    "autograde": task_orm.autograde,
                    **task_orm.other_fields,
                }
                for task_orm in definition_orm.tasks
            ],
        }
    )

    task_results: list[TaskEvalResult] = definition.run(
        submission.user_inputs, submission.expected_answers, task_id
    )
    has_pending_tasks: bool = any(
        task_result.status == TaskEvalStatus.PENDING for task_result in task_results
    )

    submission_orm = SubmissionORM(
        definition_id=id,
        status=SubmissionStatus.Pending if has_pending_tasks else SubmissionStatus.Ok,
        task_results=[
            TaskResultORM(
                definition_id=id,
                task_id=task_result.task_id,
                completed_at=sa.func.now()
                if task_result.status != TaskEvalStatus.PENDING
                else None,
                job_id=task_result.result if task_result.status == TaskEvalStatus.PENDING else None,
                status=task_result.status,
                result=task_result.result.model_dump(mode="json")
                if task_result.status != TaskEvalStatus.PENDING and task_result.result
                else None,
                error=task_result.error,
            )
            for task_result in task_results
        ],
        other_fields={},
    )

    db_session.add(submission_orm)
    db_session.commit()
    db_session.refresh(submission_orm)

    return submission_orm.task_results


@router.get("/submissions/{submission_id}", summary="Get results of a submission")
def get_submission(
    submission_id: int,
    db_session: Annotated[Session, Depends(get_db_session)],
    task_id: int | None = None,
):
    query = sa.select(TaskResultORM).join(SubmissionORM).where(SubmissionORM.id == submission_id)
    if task_id is not None:
        query = query.where(TaskResultORM.task_id == task_id)
    return db_session.execute(query).scalars().all()
