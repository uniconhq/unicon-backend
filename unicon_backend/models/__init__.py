from sqlalchemy import create_engine

from unicon_backend.helpers.constants import DATABASE_URL
from unicon_backend.models.base import Base
from unicon_backend.models.user import User

# TODO: change to postgres
engine = create_engine(DATABASE_URL, echo=True)


def initialise_tables():
    Base.metadata.create_all(engine)
