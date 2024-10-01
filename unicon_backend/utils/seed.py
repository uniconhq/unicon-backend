from sqlalchemy import delete
from sqlalchemy.orm import Session

from unicon_backend.dependencies.auth import get_password_hash
from unicon_backend.models import User, engine


def clear_db(session: Session):
    # TODO: fix this!
    session.execute(delete(User))


def seed_users(session: Session):
    test_user = User(username="admin", password=get_password_hash("admin"))
    session.add(test_user)
    session.commit()


def seed():
    with Session(engine) as session:
        clear_db(session)
        seed_users(session)


if __name__ == "__main__":
    seed()
