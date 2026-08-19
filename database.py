from sqlmodel import SQLModel, Session, create_engine

# A single file is enough - no DB server needed for the minimal build.
DATABASE_URL = "sqlite:///./fass_logistik.db"

# check_same_thread=False is standard for SQLite + FastAPI,
# because FastAPI can process requests across threads.
engine = create_engine(
    DATABASE_URL, echo=True, connect_args={"check_same_thread": False}
)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
