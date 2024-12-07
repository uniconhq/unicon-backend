from unicon_backend.database import SessionLocal


def get_db_session():
    with SessionLocal() as session:
        yield session
