from sqlalchemy import create_engine

from ..helpers.constants import DATABASE_URL
from .user import User
from .base import Base


# TODO: change to postgres
engine = create_engine(DATABASE_URL, echo=True)


def initialise_tables():
    Base.metadata.create_all(engine)
