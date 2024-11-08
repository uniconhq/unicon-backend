from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session

from unicon_backend.constants import DATABASE_URL

engine: Engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, class_=Session)
