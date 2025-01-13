import os

from dotenv import load_dotenv

load_dotenv()


def _get_env_var(name: str, default: str | None = None, required: bool = True):
    value = os.getenv(name, default) or default
    if (value is None) and required:
        raise ValueError(f"{name} environment variable not defined")
    return value


DATABASE_URL: str = _get_env_var("DATABASE_URL")
RABBITMQ_URL: str = _get_env_var("RABBITMQ_URL")
SECRET_KEY: str = _get_env_var("SECRET_KEY", "", required=False)
FRONTEND_URL: str = _get_env_var("FRONTEND_URL", required=False)

EXCHANGE_NAME = _get_env_var("EXCHANGE_NAME", "unicon")
TASK_QUEUE_NAME = _get_env_var("WORK_QUEUE_NAME", "unicon.tasks")
RESULT_QUEUE_NAME = _get_env_var("RESULT_QUEUE_NAME", "unicon.results")

PERMIFY_HOST = _get_env_var("PERMIFY_HOST", "http://localhost:3476")
SCHEMA_VERSION = _get_env_var(
    "SCHEMA_VERSION", "If you see this, run cli.py init_permify", required=False
)
