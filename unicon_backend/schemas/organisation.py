from unicon_backend.models.organisation import (
    InvitationKeyBase,
    OrganisationBase,
    ProjectBase,
    RoleBase,
)
from unicon_backend.models.problem import ProblemBase


class OrganisationCreate(OrganisationBase):
    pass


class OrganisationUpdate(OrganisationBase):
    pass


class OrganisationPublic(OrganisationBase):
    id: int


class OrganisationPublicWithProjects(OrganisationPublic):
    projects: list["ProjectPublic"]


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(ProjectBase):
    pass


class ProjectPublic(ProjectBase):
    id: int
    roles: list["RolePublic"]


class ProjectPublicWithProblems(ProjectPublic):
    problems: list[ProblemBase]


class RolePublic(RoleBase):
    id: int
    project_id: int

    view_problems_access: bool
    create_problems_access: bool
    edit_problems_access: bool
    delete_problems_access: bool

    view_restricted_problems_access: bool
    edit_restricted_problems_access: bool
    delete_restricted_problems_access: bool

    make_submission_access: bool
    view_own_submission_access: bool
    view_others_submission_access: bool


class RoleCreate(RoleBase):
    name: str


class RoleUpdate(RoleBase):
    name: str

    view_problems_access: bool
    create_problems_access: bool
    edit_problems_access: bool
    delete_problems_access: bool

    view_restricted_problems_access: bool
    edit_restricted_problems_access: bool
    delete_restricted_problems_access: bool

    make_submission_access: bool
    view_own_submission_access: bool
    view_others_submission_access: bool


class RolePublicWithInvitationKeys(RolePublic):
    invitation_keys: list["InvitationKeyPublic"]


class InvitationKeyPublic(InvitationKeyBase):
    pass
