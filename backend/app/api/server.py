from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import structlog
from pathlib import Path

from app.api.routes import router as api_router
from app.core import config


struct_logger = structlog.get_logger(__name__)


def get_application():
    app = FastAPI(title=config.PROJECT_NAME, version=config.VERSION)

    BASE_PATH = Path(__file__).resolve().parent
    STATIC_FOLDER = str(BASE_PATH / "static/")
    app.mount('/static', StaticFiles(directory=STATIC_FOLDER), name="static")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=config.API_PREFIX)

    return app


app = get_application()
