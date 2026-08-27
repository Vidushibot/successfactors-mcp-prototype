from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import DateTime, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(
        String(36), unique=True, default=lambda: str(uuid.uuid4())
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[str] = mapped_column(String(36), index=True)
    session_id: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(64))
    agent_name: Mapped[str] = mapped_column(String(64))
    tool_name: Mapped[str] = mapped_column(String(80))
    input_summary: Mapped[str] = mapped_column(String(500))
    entity: Mapped[str] = mapped_column(String(40), default="")
    business_key_hash: Mapped[str] = mapped_column(String(20), default="")
    authorization_outcome: Mapped[str] = mapped_column(String(20))
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    data_source_mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    error_category: Mapped[str] = mapped_column(String(40), default="")

    def public(self) -> dict[str, object]:
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}


class AuditRepository:
    def __init__(self, url: str) -> None:
        if url.startswith("sqlite") and "memory" not in url:
            db_path = Path(url.split("///", 1)[-1])
            db_path.parent.mkdir(parents=True, exist_ok=True)
        engine_options: dict[str, object] = {"connect_args": {"check_same_thread": False}}
        if url == "sqlite:///:memory:":
            engine_options["poolclass"] = StaticPool
        self.engine = create_engine(url, **engine_options)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self.sessions() as session:
            yield session

    def add(self, **values: object) -> AuditEvent:
        event = AuditEvent(timestamp=datetime.now(UTC), **values)
        with self.session() as session:
            session.add(event)
            session.commit()
            session.refresh(event)
        return event

    def list_for(self, user_id: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        with self.session() as session:
            statement = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(min(limit, 100))
            if user_id:
                statement = statement.where(AuditEvent.user_id == user_id)
            return [event.public() for event in session.scalars(statement)]

    def get(self, event_id: str) -> dict[str, object] | None:
        with self.session() as session:
            event = session.scalar(select(AuditEvent).where(AuditEvent.event_id == event_id))
            return event.public() if event else None


def safe_input_summary(values: dict[str, object]) -> str:
    return json.dumps(
        {key: "[provided]" if "id" in key.lower() else value for key, value in values.items()},
        default=str,
    )
