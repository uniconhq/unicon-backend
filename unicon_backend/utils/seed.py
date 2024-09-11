from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..dependencies.auth import get_password_hash
from ..models import User, engine


def clear_db(session: Session):
    session.execute(delete(User))


def seed_users(session: Session):
    test_user = User(username="admin", password=get_password_hash("admin"))
    session.add(test_user)
    session.commit()


with Session(engine) as session:
    clear_db(session)
    seed_users(session)
