from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _ensure_workflow_checkpoint_columns() -> None:
    with engine.begin() as conn:
        inspector = inspect(conn)
        if "workflows" not in inspector.get_table_names():
            return

        columns = {column["name"] for column in inspector.get_columns("workflows")}
        required_columns = {
            "checkpoint_data": "ALTER TABLE workflows ADD COLUMN checkpoint_data JSON DEFAULT '{}'",
            "last_successful_agent": "ALTER TABLE workflows ADD COLUMN last_successful_agent VARCHAR(160)",
            "last_checkpoint_at": "ALTER TABLE workflows ADD COLUMN last_checkpoint_at DATETIME",
        }

        for column_name, sql in required_columns.items():
            if column_name in columns:
                continue
            conn.execute(text(sql))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_workflow_checkpoint_columns()
