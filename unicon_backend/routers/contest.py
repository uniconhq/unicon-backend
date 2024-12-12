from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from unicon_backend.dependencies.auth import get_current_user
from unicon_backend.dependencies.common import get_db_session
from unicon_backend.evaluator.contest import ExpectedAnswer, Problem, UserInput
from unicon_backend.evaluator.tasks.base import TaskEvalResult, TaskEvalStatus
from unicon_backend.models import (
    ProblemORM,
    SubmissionORM,
    SubmissionStatus,
    TaskResultORM,
)
from unicon_backend.models.contest import SubmissionPublic, TaskAttemptORM, TaskType
from unicon_backend.models.user import UserORM

router = APIRouter(prefix="/contests", tags=["contest"], dependencies=[Depends(get_current_user)])

if TYPE_CHECKING:
    from unicon_backend.evaluator.tasks.programming.task import ProgrammingTask


@router.get("/problems", summary="Get all problems", response_model=list[ProblemORM])
def get_problems(
    db_session: Annotated[Session, Depends(get_db_session)],
):
    return db_session.exec(select(ProblemORM)).all()


@router.get("/problems/{id}", summary="Get a problem definition")
def get_problem(
    id: int,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> Problem:
    problem_orm = db_session.scalar(
        select(ProblemORM).where(ProblemORM.id == id).options(selectinload(ProblemORM.tasks))
    )

    if problem_orm is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Problem definition not found")

    problem: Problem = Problem.model_validate(
        {
            "name": problem_orm.name,
            "description": problem_orm.description,
            "tasks": [
                {
                    "id": task_orm.id,
                    "type": task_orm.type,
                    "autograde": task_orm.autograde,
                    **task_orm.other_fields,
                }
                for task_orm in problem_orm.tasks
            ],
        }
    )

    for task in problem.tasks:
        if task.type == TaskType.PROGRAMMING:
            programming_task: ProgrammingTask = task
            for testcase in programming_task.testcases:
                testcase.nodes.insert(0, programming_task.get_implicit_input_step())

    return problem


@router.patch("/problem/{id}", summary="Update a problem definition", response_model=Problem)
def update_problem(
    id: int, problem: Problem, db_session: Annotated[Session, Depends(get_db_session)]
):
    problem_orm = db_session.scalar(
        select(ProblemORM).where(ProblemORM.id == id).options(selectinload(ProblemORM.tasks))
    )

    if problem_orm is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Problem definition not found")

    # Delete existing tasks and add new ones
    for task_orm in problem_orm.tasks:
        db_session.delete(task_orm)

    # Update problem definition
    problem_orm.update(problem)

    db_session.add(problem_orm)
    db_session.commit()
    db_session.refresh(problem_orm)

    return problem_orm


class ProblemSubmission(BaseModel):
    expected_answers: list[ExpectedAnswer]
    user_inputs: list[UserInput]


@router.post("/problems/{id}/submissions", summary="Upload a problem submission")
def submit_problem_submission(
    id: int,
    submission: ProblemSubmission,
    db_session: Annotated[Session, Depends(get_db_session)],
    user: Annotated[UserORM, Depends(get_current_user)],
    task_id: int | None = None,
) -> SubmissionORM:
    problem_orm = db_session.scalar(
        select(ProblemORM).where(ProblemORM.id == id).options(selectinload(ProblemORM.tasks))
    )

    if problem_orm is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Problem definition not found")

    problem: Problem = Problem.model_validate(
        {
            "name": problem_orm.name,
            "description": problem_orm.description,
            "tasks": [
                {
                    "id": task_orm.id,
                    "type": task_orm.type,
                    "autograde": task_orm.autograde,
                    **task_orm.other_fields,
                }
                for task_orm in problem_orm.tasks
            ],
        }
    )

    task_results: list[TaskEvalResult] = problem.run(
        submission.user_inputs, submission.expected_answers, task_id
    )
    has_pending_tasks: bool = any(
        task_result.status == TaskEvalStatus.PENDING for task_result in task_results
    )

    user_input_index: dict[int, UserInput] = {
        user_input.task_id: user_input for user_input in submission.user_inputs
    }

    task_attempts = [
        TaskAttemptORM(
            problem_id=id,
            task_id=task_result.task_id,
            task_type=problem.tasks[task_result.task_id].type,
            other_fields=user_input_index[task_result.task_id].model_dump(),
            task_results=[
                TaskResultORM(
                    completed_at=sa.func.now()
                    if task_result.status != TaskEvalStatus.PENDING
                    else None,
                    job_id=task_result.result
                    if task_result.status == TaskEvalStatus.PENDING
                    else None,
                    status=task_result.status,
                    result=task_result.result.model_dump(mode="json")
                    if task_result.status != TaskEvalStatus.PENDING and task_result.result
                    else None,
                    error=task_result.error,
                    task_type=problem.tasks[task_result.task_id].type,
                )
            ],
        )
        for task_result in task_results
    ]

    submission_orm = SubmissionORM(
        user_id=user.id,
        problem_id=id,
        status=SubmissionStatus.Pending if has_pending_tasks else SubmissionStatus.Ok,
        task_attempts=task_attempts,
        other_fields={},
    )

    db_session.add(submission_orm)
    db_session.commit()
    db_session.refresh(submission_orm)

    return submission_orm


@router.get("/submissions", summary="Get all submissions", response_model=list[SubmissionPublic])
def get_submissions(
    db_session: Annotated[Session, Depends(get_db_session)],
):
    return db_session.exec(
        select(SubmissionORM).options(
            selectinload(SubmissionORM.task_attempts).selectinload(TaskAttemptORM.task_results),
            selectinload(SubmissionORM.task_attempts).selectinload(TaskAttemptORM.task),
        )
    ).all()


@router.get("/submissions/{submission_id}", summary="Get results of a submission")
def get_submission(
    submission_id: int,
    db_session: Annotated[Session, Depends(get_db_session)],
    task_id: int | None = None,
) -> SubmissionPublic:
    # TODO: handle case with more than one task attempt for same task
    query = (
        select(SubmissionORM)
        .where(SubmissionORM.id == submission_id)
        .options(
            selectinload(
                SubmissionORM.task_attempts.and_(col(TaskAttemptORM.task_id) == task_id)
                if task_id
                else SubmissionORM.task_attempts
            ).selectinload(TaskAttemptORM.task_results),
            selectinload(
                SubmissionORM.task_attempts.and_(col(TaskAttemptORM.task_id) == task_id)
                if task_id
                else SubmissionORM.task_attempts
            ).selectinload(TaskAttemptORM.task),
        )
    )

    submission = db_session.exec(query).first()
    if submission is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Submission not found")
    else:
        return SubmissionPublic.model_validate(submission)
