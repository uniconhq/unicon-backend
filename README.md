# Unicon 🦄 Backend

## Development

_`uv` is used as the package and project manager for this project. Install it by following the instructions [here](https://docs.astral.sh/uv/getting-started/installation/)._

Install dependencies:

```bash
uv sync # all dependencies
uv sync --no-dev # only production dependencies
```

Add database migrations:

```bash
# Generates new migration files under `unicon_backend/migrations/versions`
# This should be ran after making changes to any database models under `unicon_backend/models`
uv run alembic revision --autogenerate -m "<description>"
```

Run database migrations:

```bash
# Set the database URL (`DATABASE_URL`) in the .env file / environment variable
# Migration files are located under `unicon_backend/migrations`
uv run alembic upgrade head
```

Seed the database:

```bash
# By default, it seeds the database URL (`DATABASE_URL`) in the .env file / environment variable
uv run unicon_backend/cli.py seed <admin-username> <admin-password> \
    ./examples/addition/definitions/*.json \
    ./examples/problem_set/definition.json \
    ./examples/breakthrough/definition.json
```

Seed permissions:

```bash
# NOTE: Depends on the `permify` service being up and running

# Initialises the permissions schema
# By default, it initialises the schema stored at `unicon_backend/unicon.perm`
uv run unicon_backend/cli.py permify init

# Seed permission for records in the database
uv run unicon_backend/cli.py permify seed
```

Start the development server:

```bash
# Set the RabbitMQ URL (`RABBITMQ_URL`) in the .env file / environment variable
uv run fastapi dev unicon_backend/app.py
```