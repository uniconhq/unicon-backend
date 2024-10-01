from sqlalchemy.orm import Session

from unicon_backend.constants import sql_engine


def get_session():
    with Session(sql_engine) as session:
        yield session
