"""Movimientos y GPS (K05): GPS alerts, their justification and review, and field records."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Numeric,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum
from app.models.enums import (
    ActividadCampo,
    EstadoMovimiento,
    MotivoMovimiento,
    TipoCampo,
    TipoEventoMovimiento,
    TipoMovimiento,
)
from app.models.inmuebles import Inmueble
from app.models.leads import Cita
from app.models.user import User


class Movimiento(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One GPS alert (salida de ruta, tiempo detenido, salida de la zona) or one field record."""

    __tablename__ = "movimientos"
    __table_args__ = (
        CheckConstraint("fin_at IS NULL OR fin_at >= ocurrido_at", name="fechas"),
        CheckConstraint(
            "(tipo IN ('trabajo_campo', 'atencion_campo')) = (estado = 'registro')",
            name="estado_registro",
        ),
    )

    numero: Mapped[int] = mapped_column(Identity(start=1), unique=True)
    empleado_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[TipoMovimiento] = mapped_column(pg_enum(TipoMovimiento, "tipo_movimiento"))
    estado: Mapped[EstadoMovimiento] = mapped_column(
        pg_enum(EstadoMovimiento, "estado_movimiento"), index=True
    )
    ocurrido_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fin_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # field work end
    minutos_umbral: Mapped[int | None] = mapped_column(SmallInteger)  # tiempo detenido: «+20 min»
    lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    lugar: Mapped[str | None] = mapped_column(String(120))  # «Itagüí», «Laureles»

    # Justification (M05): cita / inventario → inmueble, cliente, observación;
    # personal → motivo, who authorized it (salida), evidence (tiempo detenido).
    motivo: Mapped[MotivoMovimiento | None] = mapped_column(
        pg_enum(MotivoMovimiento, "motivo_movimiento")
    )
    inmueble_codigo: Mapped[str | None] = mapped_column(String(40))
    inmueble_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inmuebles.id", ondelete="SET NULL")
    )
    cliente: Mapped[str | None] = mapped_column(String(200))
    motivo_texto: Mapped[str | None] = mapped_column(String(300))
    autorizo: Mapped[str | None] = mapped_column(String(20))  # coordinacion | gerencia | pendiente
    evidencias: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    observacion: Mapped[str | None] = mapped_column(String(500))
    justificada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Review
    revisado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    revisado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    nota_revision: Mapped[str | None] = mapped_column(String(300))

    # Field records (K16 / C09)
    tipo_campo: Mapped[TipoCampo | None] = mapped_column(pg_enum(TipoCampo, "tipo_campo"))
    actividad_campo: Mapped[ActividadCampo | None] = mapped_column(
        pg_enum(ActividadCampo, "actividad_campo")
    )
    cita_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("citas.id", ondelete="SET NULL"))
    acompanados_ids: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )  # asesores (acompañamiento en ruta / salida grupal)
    detalle: Mapped[str | None] = mapped_column(String(300))  # «captación Laureles»

    creado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )  # NULL = reported by the GPS

    empleado: Mapped[User] = relationship(foreign_keys=[empleado_id], lazy="joined")
    revisado_por: Mapped[User | None] = relationship(foreign_keys=[revisado_por_id], lazy="joined")
    cita: Mapped[Cita | None] = relationship(lazy="joined")
    inmueble: Mapped[Inmueble | None] = relationship(lazy="joined")

    @property
    def code(self) -> str:
        return f"MOV-{self.numero:04d}"

    @property
    def duracion_min(self) -> int | None:
        if self.fin_at is None:
            return None
        return int((self.fin_at - self.ocurrido_at).total_seconds() // 60)


class MovimientoEvento(UUIDPrimaryKeyMixin, Base):
    """History: who did what and when, with the state before and after (G-0xx «trazabilidad»).

    `movimiento_id` is NULL for page-wide events (configuration changes, downloads).
    """

    __tablename__ = "movimiento_eventos"

    movimiento_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("movimientos.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[TipoEventoMovimiento] = mapped_column(
        pg_enum(TipoEventoMovimiento, "tipo_evento_movimiento")
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    estado_antes: Mapped[str | None] = mapped_column(String(30))
    estado_despues: Mapped[str | None] = mapped_column(String(30))
    detalle: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )

    actor: Mapped[User | None] = relationship(lazy="joined")


class MovimientosConfig(Base):
    """Single row (id = 1): the alert time and the deadline to justify."""

    __tablename__ = "movimientos_config"
    __table_args__ = (CheckConstraint("id = 1", name="una_fila"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    minutos_alerta: Mapped[int] = mapped_column(SmallInteger, default=20, server_default="20")
    plazo_horas: Mapped[int | None] = mapped_column(SmallInteger)  # NULL = PENDIENTE DE CONFIG.
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    updated_by: Mapped[User | None] = relationship(lazy="joined")

    def as_dict(self) -> dict[str, Any]:
        return {"minutos_alerta": self.minutos_alerta, "plazo_horas": self.plazo_horas}
