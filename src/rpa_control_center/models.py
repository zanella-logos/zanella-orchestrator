"""Portable persistence models; timestamps are Unix seconds in UTC."""

import time
import uuid

from sqlalchemy import JSON, Boolean, CheckConstraint, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Robot(Base):
    __tablename__ = "robots"
    __table_args__ = (CheckConstraint("timeout > 0"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), unique=True)
    executor_type: Mapped[str] = mapped_column(String(24), default="python", server_default="python")
    script: Mapped[str] = mapped_column(Text)
    interpreter: Mapped[str] = mapped_column(Text)
    cwd: Mapped[str] = mapped_column(Text)
    arguments: Mapped[list] = mapped_column(JSON, default=list)
    timeout: Mapped[float] = mapped_column(Float, default=3600)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    robot_id: Mapped[str] = mapped_column(ForeignKey("robots.id", ondelete="CASCADE"), index=True)
    frequency: Mapped[str] = mapped_column(String(16))
    time_of_day: Mapped[str] = mapped_column(String(5))
    weekday: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    next_run_at: Mapped[float] = mapped_column(Float, index=True)
    last_run_at: Mapped[float | None] = mapped_column(Float)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    robot_id: Mapped[str] = mapped_column(ForeignKey("robots.id"))
    configuration: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    started_at: Mapped[float | None] = mapped_column(Float)
    ended_at: Mapped[float | None] = mapped_column(Float)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    business_result: Mapped[str] = mapped_column(String(24), default="not_reported")
    business_summary: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    stdout_path: Mapped[str | None] = mapped_column(Text)
    stderr_path: Mapped[str | None] = mapped_column(Text)
    result_path: Mapped[str | None] = mapped_column(Text)
    process_id: Mapped[int | None] = mapped_column(Integer)
