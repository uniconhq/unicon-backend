import logging
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from unicon_backend.dependencies.auth import get_current_user
from unicon_backend.helpers.constants import FRONTEND_URL
from unicon_backend.models import User, initialise_tables
from unicon_backend.routers.auth import router as auth_router
from unicon_backend.utils.seed import seed

logging.getLogger("passlib").setLevel(logging.ERROR)

app = FastAPI()

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
