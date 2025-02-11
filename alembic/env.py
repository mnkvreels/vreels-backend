from __future__ import with_statement
import sys
import os
from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy.ext.declarative import DeclarativeMeta
from alembic import context

# Add the app directory to the sys.path so that we can import our models
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))

DATABASE_URL = "mssql+pyodbc://sqladmin:MnkLlc%4025@sqlddatabbasedemo.database.windows.net:1433/vreeels_django_database?driver=ODBC+Driver+17+for+SQL+Server"

engine = create_engine(DATABASE_URL)

# Import the Base from all of your models
from users.models import Base as UsersBase
# from posts.models import Base as PostsBase
# from calls.models import Base as CallsBase
# from notifications.models import Base as NotificationsBase
# from accounts.models import Base as AccountsBase
# from reels.models import Base as ReelsBase

# This is where Alembic will be looking for models
target_metadata = UsersBase.metadata
# []    # UsersBase.metadata,
    # PostsBase.metadata,
    # CallsBase.metadata,
    # NotificationsBase.metadata,
    # AccountsBase.metadata,
    # ReelsBase.metadata,
# ]

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = UsersBase.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
