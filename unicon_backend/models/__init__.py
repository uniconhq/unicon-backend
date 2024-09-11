from sqlalchemy import create_engine

from ..helpers.constants import DATABASE_URL
from .base import Base
from .user import User

# TODO: change to postgres
engine = create_engine(DATABASE_URL, echo=True)


def initialise_tables():
    Base.metadata.create_all(engine)
