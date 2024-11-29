from sqlmodel import Field, Relationship, SQLModel


class Organisation(SQLModel, table=True):
    id: int = Field(primary_key=True)
    name: str
    description: str
    owner_id: int = Field(foreign_key="user.id")

    projects: list["Project"] = Relationship(back_populates="organisation")


class Project(SQLModel, table=True):
    id: int = Field(primary_key=True)
    name: str
    organisation_id: int = Field(foreign_key="organisation.id")

    organisation: Organisation = Relationship(back_populates="projects")
    roles: list["Role"] = Relationship(back_populates="project")


class Role(SQLModel, table=True):
    id: int = Field(primary_key=True)
    name: str
    project_id: int = Field(foreign_key="project.id")

    project: Project = Relationship(back_populates="roles")
    invitation_keys: list["InvitationKey"] = Relationship(back_populates="role")


class InvitationKey(SQLModel, table=True):
    id: int = Field(primary_key=True)
    key: str
    role_id: int = Field(foreign_key="role.id")

    role: Role = Relationship(back_populates="invitation_keys")
    enabled: bool
