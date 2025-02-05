import re
from typing import Any

from pydantic import BaseModel, model_validator
from sqlmodel import MetaData, SQLModel


def _camel_to_snake(name: str) -> str:
    pattern = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
    name = pattern.sub("_", name).lower()
    return name


class CustomBaseModel(BaseModel, extra="forbid"):
    __polymorphic__ = False
    __subclasses_map__: dict[str, type] = {}

    @model_validator(mode="wrap")
    @classmethod
    def __convert_to_real_type__(cls, value: Any, handler):
        if isinstance(value, dict) is False or not cls.__polymorphic__:
            return handler(value)

        if (class_full_name := value.get("type", None)) is None:
            raise ValueError("Missing type field")

        if (class_type := cls.__subclasses_map__.get(class_full_name, None)) is None:
            raise TypeError("Subclass not found")

        return class_type(**value)

    def __init_subclass__(cls, polymorphic: bool = False, **kwargs):
        cls.__polymorphic__ = polymorphic
        cls.__subclasses_map__[f"{_camel_to_snake(cls.__qualname__).upper()}"] = cls
        super().__init_subclass__(**kwargs)


class CustomSQLModel(SQLModel):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_`%(constraint_name)s`",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
