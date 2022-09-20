from typing import Callable, Type, Generator
from databases import Database
from fastapi import Depends
from app.db.repositories.base import BaseRepository
from app.core.config import SQL_ENGINE
from sqlalchemy.orm import sessionmaker


def get_database() -> Generator:
    Session = sessionmaker(bind=SQL_ENGINE, autocommit=True, expire_on_commit=False, )
    return Session


def get_repository(Repo_type: Type[BaseRepository]) -> Callable:
    def get_repo(db: Database = Depends(get_database)) -> Type[BaseRepository]:
        return Repo_type(db)

    return get_repo
