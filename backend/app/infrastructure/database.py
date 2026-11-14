from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base; domain models arrive in later stages, not in the bootstrap."""


_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": _settings.database_connect_timeout},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session]:
    with SessionLocal() as session:
        yield session


def check_database_connection(session: Session) -> None:
    session.execute(text("SELECT 1"))
