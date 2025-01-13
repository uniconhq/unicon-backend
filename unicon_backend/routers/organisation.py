from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from unicon_backend.dependencies.auth import get_current_user
from unicon_backend.dependencies.common import get_db_session
from unicon_backend.dependencies.organisation import get_organisation_by_id
from unicon_backend.dependencies.project import create_project_with_defaults
from unicon_backend.lib.permissions.permission import permission_create
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
    organisations = db_session.exec(
        select(Organisation).where(Organisation.owner_id == user.id)
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
    return organisation


@router.put("/{id}", summary="Update an organisation", response_model=OrganisationPublic)
def update_organisation(
    update_data: OrganisationUpdate,
    db_session: Annotated[Session, Depends(get_db_session)],
    organisation: Annotated[Organisation, Depends(get_organisation_by_id)],
):
    organisation.sqlmodel_update(update_data)
    db_session.commit()
    db_session.refresh(organisation)
    return organisation


@router.delete("/{id}", summary="Delete an organisation")
def delete_organisation(
    db_session: Annotated[Session, Depends(get_db_session)],
    organisation: Annotated[Organisation, Depends(get_organisation_by_id)],
):
    db_session.delete(organisation)
    db_session.commit()
    return


@router.get(
    "/{id}", summary="Get an organisation by ID", response_model=OrganisationPublicWithProjects
)
def get_organisation(
    organisation: Annotated[Organisation, Depends(get_organisation_by_id)],
):
    return organisation


@router.post("/{id}/projects", summary="Create a new project", response_model=ProjectPublic)
def create_project(
    user: Annotated[UserORM, Depends(get_current_user)],
    create_data: ProjectCreate,
    db_session: Annotated[Session, Depends(get_db_session)],
    organisation: Annotated[Organisation, Depends(get_organisation_by_id)],
):
    assert organisation.id is not None
    project = create_project_with_defaults(create_data, organisation.id, user)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    # Update permission records
    permission_create(project)
    for role in project.roles:
        permission_create(role)

    return project
