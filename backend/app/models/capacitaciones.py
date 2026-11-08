"""Capacitaciones (X07 «Capacitaciones del equipo», Z03 «Mis capacitaciones»; G-046, G-047)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User


class Capacitacion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A training: programmed by the Auxiliar, Coordinación or Gerencia («programada»), or one a
    person registers having attended («registrada»)."""

    __tablename__ = "capacitaciones"

    numero: Mapped[int] = mapped_column(Identity(start=1), unique=True)
    origen: Mapped[str] = mapped_column(String(12))  # programada · registrada
    tema: Mapped[str] = mapped_column(String(200))
    area: Mapped[str] = mapped_column(String(60))
    presenta: Mapped[str] = mapped_column(String(200))
    lugar: Mapped[str | None] = mapped_column(String(300))  # room or video-call link
    inicio_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # programada · realizada · cancelada (a registered one is «realizada» from the start)
    estado: Mapped[str] = mapped_column(String(12), default="programada", index=True)
    participantes_txt: Mapped[str | None] = mapped_column(String(60))  # «Todo el equipo», …
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    completada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completada_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    cancelada_motivo: Mapped[str | None] = mapped_column(String(300))

    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="joined")
    participantes: Mapped[list["CapacitacionParticipante"]] = relationship(
        back_populates="capacitacion",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="CapacitacionParticipante.created_at",
    )

    @property
    def code(self) -> str:
        return f"CAP-{self.numero:03d}"


class CapacitacionParticipante(UUIDPrimaryKeyMixin, Base):
    """One person in a training: their answer (accept / can't, with a reason), whether they
    attended once it's completed, and what they learned."""

    __tablename__ = "capacitacion_participantes"
    __table_args__ = (UniqueConstraint("capacitacion_id", "user_id"),)

    capacitacion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capacitaciones.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    respuesta: Mapped[str] = mapped_column(String(10), default="pendiente")  # pendiente·acepta·no
    motivo: Mapped[str | None] = mapped_column(String(60))
    motivo_detalle: Mapped[str | None] = mapped_column(String(300))
    respondida_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    asistio: Mapped[bool | None] = mapped_column(Boolean)  # set when the training is completed
    aprendio: Mapped[str | None] = mapped_column(Text)
    observaciones: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )

    capacitacion: Mapped[Capacitacion] = relationship(back_populates="participantes")
    user: Mapped[User] = relationship(lazy="joined")


class CapacitacionEvento(UUIDPrimaryKeyMixin, Base):
    """Every programming, answer, completion and cancellation («Registro de cambios»)."""

    __tablename__ = "capacitacion_eventos"

    capacitacion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capacitaciones.id", ondelete="CASCADE"), index=True
    )
    accion: Mapped[str] = mapped_column(String(200))
    detalle: Mapped[str | None] = mapped_column(String(500))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False, index=True
    )

    capacitacion: Mapped[Capacitacion] = relationship(lazy="joined")
    actor: Mapped[User | None] = relationship(lazy="joined")
