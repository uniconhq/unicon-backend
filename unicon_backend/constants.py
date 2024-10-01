import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()


def _get_env_var(name: str, default: str | None = None, required: bool = True):
    value = os.getenv(name, default)
    if (value is None) and required:
        raise ValueError(f"{name} environment variable not defined")
    return value


DATABASE_URL: str = _get_env_var("DATABASE_URL")
RABBITMQ_URL: str = _get_env_var("RABBITMQ_URL")

##################
#  auth configs  #
##################

SECRET_KEY: str = _get_env_var("SECRET_KEY", "", required=False)
FRONTEND_URL: str = _get_env_var("FRONTEND_URL", required=False)

sql_engine = create_engine(DATABASE_URL)
