import os

from dotenv import load_dotenv

load_dotenv()

if (DATABASE_URL := os.getenv("DATABASE_URL")) is None:
    raise ValueError("DATABASE_URL environment variable not defined")

##################
#  auth configs  #
##################

SECRET_KEY = os.getenv("SECRET_KEY")
FRONTEND_URL = os.getenv("FRONTEND_URL")
RUNNER_URL = os.getenv("RUNNER_URL")
