from pydantic import BaseModel, ConfigDict, model_validator

from unicon_backend.schemas.auth import UserPublic, UserPublicWithRoles


class MiniGroupPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class MiniGroupMemberPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    is_supervisor: bool
    user: UserPublic


class GroupMemberPublicWithGroup(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    is_supervisor: bool
    group: MiniGroupPublic


class UserPublicWithRolesAndGroups(UserPublicWithRoles):
    group_members: list[GroupMemberPublicWithGroup]


class GroupPublic(MiniGroupPublic):
    members: list[MiniGroupMemberPublic]


class GroupCreate(BaseModel):
    name: str


class GroupUpdate(GroupCreate):
    members: list[int]
    supervisors: list[int]

    @model_validator(mode="after")
    def check_supervisors_and_members(self):
        if len(set(self.members)) != len(self.members):
            raise ValueError("members should not contain duplicates")
        if len(set(self.supervisors)) != len(self.supervisors):
            raise ValueError("supervisors should not contain duplicates")
        if set(self.members) & set(self.supervisors):
            raise ValueError("supervisors and members should not overlap")
        return self
