FROM ghcr.io/astral-sh/uv:0.5.2-python3.12-alpine

ADD . /unicon-backend
WORKDIR /unicon-backend

# Install dependencies
RUN uv sync --frozen --no-dev

CMD ["uv", "run", "fastapi", "run", "unicon_backend/app.py", "--port", "9000"]