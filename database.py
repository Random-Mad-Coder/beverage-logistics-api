from sqlmodel import SQLModel, Session, create_engine

# Eine Datei reicht - kein DB-Server nötig für den Minimalbuild.
DATABASE_URL = "sqlite:///./fass_logistik.db"

# check_same_thread=False ist bei SQLite + FastAPI Standard,
# weil FastAPI Requests in Threads verarbeiten kann.
engine = create_engine(
    DATABASE_URL, echo=True, connect_args={"check_same_thread": False}
)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
