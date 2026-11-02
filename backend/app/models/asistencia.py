"""Asistencia (G-048 … G-051, Z04, K17, X08): sedes, where each person checks in, and one
attendance record per person and day with its entrada, salida and the reviews they need."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User


class Sede(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sedes"

    nombre: Mapped[str] = mapped_column(String(120))
    direccion: Mapped[str] = mapped_column(String(300))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    radio_m: Mapped[int] = mapped_column(SmallInteger, default=100, server_default="100")
    principal: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    activa: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class UbicacionAsignada(Base):
    """The sede where a person checks in when they're not on a route (default: the main one)."""

    __tablename__ = "ubicaciones_asignadas"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    sede_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sedes.id", ondelete="CASCADE"))
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sede: Mapped[Sede] = relationship(lazy="joined")
    updated_by: Mapped[User | None] = relationship(foreign_keys=[updated_by_id], lazy="joined")


class Marcacion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "marcaciones"
    __table_args__ = (UniqueConstraint("user_id", "fecha"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    fecha: Mapped[date] = mapped_column(Date, index=True)
    asignada: Mapped[str] = mapped_column(
        String(120)
    )  # «Oficina · Sede principal», «En ruta · Belén»
    # ---- entrada
    entrada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entrada_lat: Mapped[float | None] = mapped_column(Float)
    entrada_lng: Mapped[float | None] = mapped_column(Float)
    entrada_lugar: Mapped[str | None] = mapped_column(
        String(120)
    )  # «Sede principal ✓», «A 1,8 km ✕»
    entrada_dentro: Mapped[bool | None] = mapped_column(Boolean)
    # a_tiempo · impuntual · por_aprobar · aceptada · rechazada
    entrada_estado: Mapped[str | None] = mapped_column(String(15))
    minutos_tarde: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    entrada_motivo: Mapped[str | None] = mapped_column(String(30))  # cambio_solicitado · imprevisto
    entrada_texto: Mapped[str | None] = mapped_column(String(500))
    entrada_revisada_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    entrada_revisada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # ---- salida
    salida_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    salida_lat: Mapped[float | None] = mapped_column(Float)
    salida_lng: Mapped[float | None] = mapped_column(Float)
    # marcada · anticipada · extra (what happened) and its review
    salida_tipo: Mapped[str | None] = mapped_column(String(15))
    salida_estado: Mapped[str | None] = mapped_column(
        String(15)
    )  # ok · por_aprobar · aceptada · rechazada
    minutos_antes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    minutos_extra: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    salida_motivo: Mapped[str | None] = mapped_column(String(30))  # imprevisto · permiso
    salida_texto: Mapped[str | None] = mapped_column(String(500))
    salida_revisada_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # Horas extra of asesores and Atención need Coordinación AND the Auxiliar (K17)
    extra_coord: Mapped[bool | None] = mapped_column(Boolean)
    extra_aux: Mapped[bool | None] = mapped_column(Boolean)

    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="joined")


class AsistenciaEvento(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "asistencia_eventos"

    marcacion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("marcaciones.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    registro: Mapped[str] = mapped_column(String(200))
    accion: Mapped[str] = mapped_column(String(200))
    antes: Mapped[str | None] = mapped_column(String(300))
    despues: Mapped[str | None] = mapped_column(String(500))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False, index=True
    )

    actor: Mapped[User | None] = relationship(foreign_keys=[actor_id], lazy="joined")
