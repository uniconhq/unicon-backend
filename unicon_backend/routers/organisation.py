from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, select

from unicon_backend.dependencies.auth import get_current_user
from unicon_backend.dependencies.common import get_db_session
from unicon_backend.dependencies.organisation import get_organisation_by_id
from unicon_backend.dependencies.project import create_project_with_defaults
from unicon_backend.lib.permissions.permission import (
    permission_check,
    permission_create,
    permission_list_for_subject,
    permission_lookup,
)
from unicon_backend.models import Organisation, UserORM
from unicon_backend.schemas.organisation import (
    OrganisationCreate,
    OrganisationPublic,
    OrganisationPublicWithProjects,
    OrganisationUpdate,
    ProjectCreate,
    ProjectPublic,
)

router = APIRouter(
    prefix="/organisations", tags=["organisation"], dependencies=[Depends(get_current_user)]
)


@router.get("/", summary="Get all organisations that user owns", response_model=list[Organisation])
def get_all_organisations(
    db_session: Annotated[Session, Depends(get_db_session)],
    user: Annotated[UserORM, Depends(get_current_user)],
):
    accessible_organisation_ids = permission_lookup(Organisation, "view", user)
    organisations = db_session.exec(
        select(Organisation).where(col(Organisation.id).in_(accessible_organisation_ids))
    ).all()
    return organisations


@router.post("/", summary="Create a new organisation", response_model=OrganisationPublic)
def create_organisation(
    create_data: OrganisationCreate,
    db_session: Annotated[Session, Depends(get_db_session)],
    user: Annotated[UserORM, Depends(get_current_user)],
):
    organisation = Organisation.model_validate({**create_data.model_dump(), "owner_id": user.id})
    db_session.add(organisation)
    db_session.commit()
    db_session.refresh(organisation)

    permission_create(organisation)

    return organisation


@router.put("/{id}", summary="Update an organisation", response_model=OrganisationPublic)
def update_organisation(
    update_data: OrganisationUpdate,
    db_session: Annotated[Session, Depends(get_db_session)],
    organisation: Annotated[Organisation, Depends(get_organisation_by_id)],
    user: Annotated[UserORM, Depends(get_current_user)],
):
    if not permission_check(organisation, "edit", user):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Permission denied")

    organisation.sqlmodel_update(update_data)
    db_session.commit()
    db_session.refresh(organisation)
    return organisation


@router.delete("/{id}", summary="Delete an organisation")
def delete_organisation(
    db_session: Annotated[Session, Depends(get_db_session)],
    organisation: Annotated[Organisation, Depends(get_organisation_by_id)],
    user: Annotated[UserORM, Depends(get_current_user)],
):
    if not permission_check(organisation, "delete", user):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Permission denied")

    db_session.delete(organisation)
    db_session.commit()
    return


@router.get(
    "/{id}", summary="Get an organisation by ID", response_model=OrganisationPublicWithProjects
)
def get_organisation(
    organisation: Annotated[Organisation, Depends(get_organisation_by_id)],
    user: Annotated[UserORM, Depends(get_current_user)],
):
    if not permission_check(organisation, "view", user):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Permission denied")

    projects = []
    for project in organisation.projects:
        permissions = permission_list_for_subject(project, user)
        projects.append(ProjectPublic.model_validate(project, update=permissions))

    return OrganisationPublicWithProjects.model_validate(
        organisation, update={"projects": projects}
    )


@router.post("/{id}/projects", summary="Create a new project", response_model=ProjectPublic)
def create_project(
    user: Annotated[UserORM, Depends(get_current_user)],
    create_data: ProjectCreate,
    db_session: Annotated[Session, Depends(get_db_session)],
    organisation: Annotated[Organisation, Depends(get_organisation_by_id)],
):
    if not permission_check(organisation, "edit", user):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Permission denied")

    assert organisation.id is not None
    project = create_project_with_defaults(create_data, organisation.id, user)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    # Update permission records
    permission_create(project)
    for role in project.roles:
        permission_create(role)

    # Return permission in project
    permissions = permission_list_for_subject(project, user)
    result = ProjectPublic.model_validate(project, update=permissions)

    return result
