import os
from typing import Final

from dotenv import load_dotenv

load_dotenv()


def _get_env_var(name: str, default: str | None = None, required: bool = True):
    value = os.getenv(name, default) or default
    if (value is None) and required:
        raise ValueError(f"{name} environment variable not defined")
    return value


DATABASE_URL: Final[str] = _get_env_var("DATABASE_URL")

FRONTEND_URL: Final[str] = _get_env_var("FRONTEND_URL", "http://localhost:5173")

SECRET_KEY: Final[str] = _get_env_var("SECRET_KEY", "")

RABBITMQ_URL: Final[str] = _get_env_var("RABBITMQ_URL")
EXCHANGE_NAME: Final[str] = _get_env_var("EXCHANGE_NAME", "unicon")
TASK_QUEUE_NAME: Final[str] = _get_env_var("WORK_QUEUE_NAME", "unicon.tasks")
RESULT_QUEUE_NAME: Final[str] = _get_env_var("RESULT_QUEUE_NAME", "unicon.results")

PERMIFY_HOST: Final[str] = _get_env_var("PERMIFY_HOST", "http://localhost:3476")
PERMIFY_SCHEMA_VERSION: Final[str | None] = _get_env_var("PERMIFY_SCHEMA_VERSION", required=False)
