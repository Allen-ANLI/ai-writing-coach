from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings
from app.infrastructure.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Keep the URL out of ConfigParser (set_main_option/get_main_option): its '%'
# interpolation mangles percent-encoded credentials such as 'p%40ss'.
settings = get_settings()
database_url = settings.database_url

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = database_url
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # Without a timeout, a blackholed address (e.g. ::1 when the container
        # binds IPv4 loopback only) would hang the migration indefinitely.
        connect_args={"connect_timeout": settings.database_connect_timeout},
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
