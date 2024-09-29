import logging
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from unicon_backend.dependencies.auth import get_current_user
from unicon_backend.evaluator.contest import Definition, ExpectedAnswers, TaskResult, UserInputs
from unicon_backend.helpers.constants import FRONTEND_URL
from unicon_backend.logger import setup_rich_logger
from unicon_backend.models import User, initialise_tables
from unicon_backend.routers.auth import router as auth_router
from unicon_backend.utils.seed import seed

logging.getLogger("passlib").setLevel(logging.ERROR)

app = FastAPI()
setup_rich_logger()

origins = [FRONTEND_URL]

initialise_tables()
seed()


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

# TODO: these routes are to demonstrate authentication. Remove once we actually have other content.


@app.get("/noauth")
def no_auth():
    return "success"


@app.get("/auth")
def auth(user: Annotated[User, Depends(get_current_user)]):
    return f"success, hi {user.username}"


class Submission(BaseModel):
    definition: Definition
    expected_answers: ExpectedAnswers
    user_inputs: UserInputs


@app.post("/submit")
def submit(
    submission: Submission, _user: Annotated[User, Depends(get_current_user)]
) -> list[TaskResult]:
    return submission.definition.run(submission.user_inputs, submission.expected_answers)
