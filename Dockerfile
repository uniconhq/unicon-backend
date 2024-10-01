FROM python:3.11.9

# Install astral/uv
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.cargo/bin/:$PATH"

ADD . /unicon-backend
WORKDIR /unicon-backend

# Install dependencies
RUN uv sync --frozen --no-dev

CMD ["uv", "run", "fastapi", "run", "unicon_backend/app.py", "--port", "9000"]