# Unicon 🦄 Backend

## Development

_`uv` is used as the package and project manager for this project. Install it by following the instructions [here](https://docs.astral.sh/uv/getting-started/installation/)._

Install dependencies:

```bash
uv sync # all dependencies
uv sync --no-dev # only production dependencies
```

Run database migrations:

```bash
# Set the database URL (`DATABASE_URL`) in the .env file / environment variable
# Migration files are located under `unicon_backend/migrations`
uv run alembic upgrade head
```

Add database migrations:

```bash
# Generates new migration files under `unicon_backend/migrations/versions`
# This should be ran after making changes to any database models under `unicon_backend/models`
uv run alembic revision --autogenerate -m "<description>"
```

Start the development server:

```bash
# Set the RabbitMQ URL (`RABBITMQ_URL`) in the .env file / environment variable
uv run fastapi dev unicon_backend/app.py
```