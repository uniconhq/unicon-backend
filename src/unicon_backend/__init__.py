

from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from .routers.auth import router as auth_router
from .helpers.constants import FRONTEND_URL
from .models import initialise_tables

app = FastAPI()

origins = [
    FRONTEND_URL
]

initialise_tables()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(auth_router)
