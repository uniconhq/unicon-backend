import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from unicon_backend.constants import FRONTEND_URL
from unicon_backend.logger import setup_rich_logger
from unicon_backend.routers import auth, contest
from unicon_backend.workers import task_publisher, task_results_consumer

# `passlib` has a known issue with one of its dependencies which causes it to log a non-consequential warning.
# We suppress this warning to avoid confusion
# Reference: https://github.com/pyca/bcrypt/issues/684
logging.getLogger("passlib.handlers.bcrypt").setLevel(logging.ERROR)
setup_rich_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _event_loop = asyncio.get_event_loop()
    task_results_consumer.run(event_loop=_event_loop)
    task_publisher.run(event_loop=_event_loop)

    yield

    task_publisher.stop()
    task_results_consumer.stop()


app = FastAPI(title="Unicon 🦄 Backend", lifespan=lifespan, separate_input_output_schemas=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(contest.router)

# Set `operation_id` for all routes to the same as the `name`
# This is done to make the generated OpenAPI documentation more readable
for route in app.routes:
    if isinstance(route, APIRoute):
        route.operation_id = route.name
