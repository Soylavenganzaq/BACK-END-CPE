import os
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')


class DatabaseNotConfigured(RuntimeError):
    pass


_engine = None


def create_database_engine(database_url: str | None = None):
    url = database_url or DATABASE_URL
    if not url:
        raise DatabaseNotConfigured('DATABASE_URL no está configurada.')

    parsed_url = make_url(url)
    if parsed_url.get_backend_name() != 'postgresql':
        raise ValueError('DATABASE_URL debe apuntar a PostgreSQL.')
    if parsed_url.drivername == 'postgresql':
        parsed_url = parsed_url.set(drivername='postgresql+psycopg')
    return create_engine(parsed_url, pool_pre_ping=True)


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_database_engine()
    return _engine


def get_db_session():
    return sessionmaker(bind=get_engine(), expire_on_commit=False)()
