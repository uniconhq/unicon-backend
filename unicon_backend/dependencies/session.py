from sqlalchemy.orm import Session

from unicon_backend.models import engine


def get_session():
    with Session(engine) as session:
        yield session
