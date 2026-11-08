"""Pausas activas (G11; decisions G-041, G-045, G-060, G-065)."""

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.user import User


class PausaConfig(Base):
    """One row (id = 1): the two daily times, how long the reminder stays and its message."""

    __tablename__ = "pausas_config"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    hora_manana: Mapped[time] = mapped_column(Time)
    hora_tarde: Mapped[time] = mapped_column(Time)
    minutos: Mapped[int] = mapped_column(SmallInteger)  # reminder on screen (G-060)
    mensaje: Mapped[str] = mapped_column(String(300))
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )


class PausaActiva(UUIDPrimaryKeyMixin, Base):
    """A pause someone marked «Realizada». No row = not done (computed for past windows)."""

    __tablename__ = "pausas_activas"
    __table_args__ = (UniqueConstraint("user_id", "fecha", "turno"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    fecha: Mapped[date] = mapped_column(Date, index=True)
    turno: Mapped[str] = mapped_column(String(6))  # manana · tarde
    programada: Mapped[time] = mapped_column(Time)  # the scheduled time that day
    realizada_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(lazy="joined")
