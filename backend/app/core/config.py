import structlog
from sqlalchemy import create_engine
from starlette.config import Config
from starlette.datastructures import Secret
import os

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

struct_logger = structlog.get_logger(__name__)

# Project Details

# Use .env file only if it exists, otherwise rely on environment variables
if os.path.exists(".env"):
    config = Config(".env")
else:
    # Use environment variables directly without .env file (for Azure deployment)
    config = Config(environ=os.environ)
PROJECT_NAME = "Taxmoja by Paymoja"
VERSION = "1.0.0"
API_PREFIX = ""

# Settings File

SETTINGS_FILE = config("SETTINGS_FILE", cast=str)

# Database Configuration
MYSQL_USER = config("MYSQL_USER", cast=str)
MYSQL_PASSWORD = config("MYSQL_PASSWORD", cast=Secret)
MYSQL_HOST = config("MYSQL_HOST", cast=str, default="taxmoja-api")
MYSQL_PORT = config("MYSQL_PORT", cast=str, default="5432")
MYSQL_DB = config("MYSQL_DATABASE", cast=str)

# SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"

SQLALCHEMY_DATABASE_URL = 'postgresql://{}:{}@{}:{}/{}'.format(MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_PORT,
                                                               MYSQL_DB)

SQL_ENGINE = create_engine(
        SQLALCHEMY_DATABASE_URL,
        echo=True,
        pool_pre_ping=True,
        pool_size=60,
        max_overflow=0
    )

