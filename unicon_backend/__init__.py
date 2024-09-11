import logging
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .dependencies.auth import get_current_user
from .helpers.constants import FRONTEND_URL
from .models import User, initialise_tables
from .routers.auth import router as auth_router

logging.getLogger("passlib").setLevel(logging.ERROR)

app = FastAPI()

origins = [FRONTEND_URL]

initialise_tables()


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
