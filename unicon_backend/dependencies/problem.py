from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from unicon_backend.dependencies.common import get_db_session
from unicon_backend.models.contest import ProblemORM


def get_problem_by_id(
    id: int,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> ProblemORM:
    if (
        problem_orm := db_session.scalar(
            select(ProblemORM).where(ProblemORM.id == id).options(selectinload(ProblemORM.tasks))
        )
    ) is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Problem definition not found!")
    return problem_orm
