from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from unicon_backend.dependencies.auth import get_current_user
from unicon_backend.dependencies.common import get_db_session
from unicon_backend.dependencies.problem import get_problem_by_id
from unicon_backend.evaluator.problem import Problem, UserInput
from unicon_backend.models import (
    ProblemORM,
    SubmissionORM,
    TaskResultORM,
)
from unicon_backend.models.problem import SubmissionPublic, TaskAttemptORM, TaskAttemptPublic
from unicon_backend.models.user import UserORM

if TYPE_CHECKING:
    from unicon_backend.evaluator.tasks.base import TaskEvalResult

router = APIRouter(prefix="/problems", tags=["problem"], dependencies=[Depends(get_current_user)])


@router.get("/{id}", summary="Get a problem definition")
def get_problem(
    problem_orm: Annotated[ProblemORM, Depends(get_problem_by_id)],
) -> Problem:
    return problem_orm.to_problem()


@router.patch("/{id}", summary="Update a problem definition")
def update_problem(
    existing_problem_orm: Annotated[ProblemORM, Depends(get_problem_by_id)],
    new_problem: Problem,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> Problem:
    # Delete existing tasks and add new ones
    for task_orm in existing_problem_orm.tasks:
        db_session.delete(task_orm)

    # Update problem definition
    existing_problem_orm.update(new_problem)

    db_session.add(existing_problem_orm)
    db_session.commit()
    db_session.refresh(existing_problem_orm)

    return existing_problem_orm.to_problem()


@router.post(
    "/{id}/tasks/{task_id}", summary="Submit a task attempt", response_model=TaskAttemptPublic
)
def submit_problem_task_attempt(
    user_input: UserInput,
    task_id: int,
    problem_orm: Annotated[ProblemORM, Depends(get_problem_by_id)],
    db_session: Annotated[Session, Depends(get_db_session)],
    user: Annotated[UserORM, Depends(get_current_user)],
):
    problem: Problem = problem_orm.to_problem()
    task_type = problem.task_index[task_id].type
    # TODO: Retrieve expected answers (https://github.com/uniconhq/unicon-backend/issues/12)
    task_attempt_orm: TaskAttemptORM = TaskAttemptORM(
        user_id=user.id,
        problem_id=problem_orm.id,
        task_id=task_id,
        task_type=task_type,
        other_fields={"user_input": user_input.value},
    )

    task_result: TaskEvalResult = problem.run_task(task_id, user_input.value, None)
    task_result_orm: TaskResultORM = TaskResultORM.from_task_eval_result(
        task_result, attempt_id=task_attempt_orm.id, task_type=task_type
    )
    task_attempt_orm.task_results.append(task_result_orm)

    db_session.add_all([task_result_orm, task_attempt_orm])
    db_session.commit()
    db_session.refresh(task_attempt_orm)

    return task_attempt_orm


@router.post("/{id}/submit", summary="Make a problem submission")
def make_submission(
    attempt_ids: list[int],
    problem_orm: Annotated[ProblemORM, Depends(get_problem_by_id)],
    user: Annotated[UserORM, Depends(get_current_user)],
    db_session: Annotated[Session, Depends(get_db_session)],
):
    submission_orm = SubmissionORM(problem_id=problem_orm.id, user_id=user.id)
    task_attempts = db_session.scalars(
        select(TaskAttemptORM)
        .where(col(TaskAttemptORM.id).in_(attempt_ids))
        .where(TaskAttemptORM.user_id == user.id)
    )

    for task_attempt in task_attempts:
        task_attempt.submissions.append(submission_orm)
        db_session.add(task_attempt)
    db_session.add(submission_orm)

    db_session.commit()
    db_session.refresh(submission_orm)

    return submission_orm


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
            selectinload(SubmissionORM.task_attempts).selectinload(TaskAttemptORM.task_results),
            selectinload(SubmissionORM.task_attempts).selectinload(TaskAttemptORM.task),
        )
    )

    if task_id is not None:
        query = query.where(TaskAttemptORM.task_id == task_id)

    # Execute query and handle not found case
    submission = db_session.exec(query).first()
    if submission is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Submission not found")

    return SubmissionPublic.model_validate(submission)
