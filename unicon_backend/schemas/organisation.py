from unicon_backend.models.organisation import OrganisationBase, ProjectBase, RoleBase


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


class RolePublic(RoleBase):
    pass
