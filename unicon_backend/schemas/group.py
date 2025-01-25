from pydantic import BaseModel, model_validator

from unicon_backend.schemas.auth import UserPublic


class MiniGroupPublic(BaseModel):
    id: int
    name: str


class GroupPublic(MiniGroupPublic):
    members: list[UserPublic]
    supervisors: list[UserPublic]


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
