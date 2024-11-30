from unicon_backend.models.organisation import Project, Role
from unicon_backend.models.user import UserORM
from unicon_backend.schemas.organisation import ProjectCreate

OWNER_ROLE = "Owner"
DEFAULT_ROLES = [OWNER_ROLE, "Helper", "Member"]


def create_project_with_defaults(
    create_data: ProjectCreate, organisation_id: int, user: UserORM
) -> Project:
    new_project = Project.model_validate(
        {**create_data.model_dump(), "organisation_id": organisation_id}
    )

    # Create three default roles
    roles = [Role(name=role_name, project=new_project) for role_name in DEFAULT_ROLES]
    new_project.roles = roles
    adminstrator_role = roles[0]

    # Make owner admin
    user.roles.append(adminstrator_role)

    # TODO: add permission to roles

    return new_project
