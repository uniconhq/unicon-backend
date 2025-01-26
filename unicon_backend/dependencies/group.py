from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlmodel import Session

from unicon_backend.dependencies.common import get_db_session
from unicon_backend.models.links import GroupMember
from unicon_backend.models.organisation import Group
from unicon_backend.models.problem import SubmissionORM
from unicon_backend.models.user import UserORM


def get_group_by_id(
    id: int,
    db_session: Annotated[Session, Depends(get_db_session)],
):
    group = db_session.scalar(
        select(Group)
        .where(Group.id == id)
        .options(
            selectinload(Group.members)
            .selectinload(GroupMember.user)
            .selectinload(UserORM.submissions)
            .selectinload(SubmissionORM.problem)
        )
    )
    if not group:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Group not found")
    return group
