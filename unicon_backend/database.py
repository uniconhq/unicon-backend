from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

from unicon_backend.constants import DATABASE_URL

engine: Engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
