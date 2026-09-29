import os

from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import event

def enable_foreign_keys(engine):
    @event.listens_for(engine, "connect")
    def listener_connect(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session

# A single file is enough - no DB server needed for the minimal build.
DATABASE_URL = "sqlite:///./beverage_logistics.db"

# SQL statement logging is off by default; set SQL_ECHO=true to enable it.
SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"

# check_same_thread=False is standard for SQLite + FastAPI,
# because FastAPI can process requests across threads.
engine = create_engine(
    DATABASE_URL, echo=SQL_ECHO, connect_args={"check_same_thread": False}
)

enable_foreign_keys(engine)