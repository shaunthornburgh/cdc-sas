"""Pólizas (X11, G-087, G-075, G-072, G-084, G-034): rental policies, insurers and their products.

Only rentals carry a policy. A policy belongs to a closed rental deal (`Cierre`, NEG-…) and/or a
property, goes through its study (en estudio → aprobada / negada, «retomar el estudio» once
negada), waits for the contract signature and is activated within the insurer's deadline.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    false,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.compensacion import Cierre
from app.models.inmuebles import Inmueble
from app.models.user import User


class Aseguradora(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "aseguradoras"

    nombre: Mapped[str] = mapped_column(String(120))
    nit: Mapped[str | None] = mapped_column(String(40))
    contacto: Mapped[str | None] = mapped_column(String(120))
    telefono: Mapped[str | None] = mapped_column(String(200))  # phone or e-mail
    activa: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # G-087: days from the contract signature to activate the policy, and when to warn
    dias_max: Mapped[int] = mapped_column(SmallInteger, default=60, server_default="60")
    aviso_dias: Mapped[int] = mapped_column(SmallInteger, default=10, server_default="10")
    ejemplo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    eliminada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    eliminada_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="joined")
    eliminada_por: Mapped[User | None] = relationship(
        foreign_keys=[eliminada_por_id], lazy="joined"
    )
    productos: Mapped[list["PolizaTipo"]] = relationship(
        back_populates="aseguradora", order_by="PolizaTipo.nombre", lazy="selectin"
    )


class PolizaTipo(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A policy an insurer offers (G-075): price as % of the rent, study, response, coverages."""

    __tablename__ = "poliza_tipos"

    aseguradora_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aseguradoras.id", ondelete="CASCADE"), index=True
    )
    nombre: Mapped[str] = mapped_column(String(120))
    precio_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))  # % of the rent, each month
    costo_estudio: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    dias_respuesta: Mapped[int | None] = mapped_column(SmallInteger)  # business days
    coberturas: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    activa: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    aseguradora: Mapped[Aseguradora] = relationship(back_populates="productos", lazy="joined")


class Poliza(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "polizas"

    cierre_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cierres.id", ondelete="SET NULL"), index=True
    )
    inmueble_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inmuebles.id", ondelete="SET NULL"), index=True
    )
    descripcion: Mapped[str | None] = mapped_column(String(200))  # when there's no property
    tipo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("poliza_tipos.id", ondelete="RESTRICT"))
    aseguradora_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aseguradoras.id", ondelete="RESTRICT"), index=True
    )
    canon: Mapped[int] = mapped_column(BigInteger)  # COP per month
    # en_estudio · aprobada · negada · activa · terminada
    estado: Mapped[str] = mapped_column(String(15), default="en_estudio", index=True)
    radicado: Mapped[str | None] = mapped_column(String(80))  # study filing number
    estudio_fecha: Mapped[date] = mapped_column(Date)
    decision_fecha: Mapped[date | None] = mapped_column(Date)
    motivo_negada: Mapped[str | None] = mapped_column(String(300))
    estudios: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1")
    retomada_motivo: Mapped[str | None] = mapped_column(String(300))
    recuperada: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    firma_fecha: Mapped[date | None] = mapped_column(Date)  # rental contract signed
    activada_fecha: Mapped[date | None] = mapped_column(Date, index=True)
    numero_poliza: Mapped[str | None] = mapped_column(String(80))
    soporte: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    seguro_inmueble: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    terminada_fecha: Mapped[date | None] = mapped_column(Date)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    eliminada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    eliminada_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    eliminada_motivo: Mapped[str | None] = mapped_column(String(300))

    cierre: Mapped[Cierre | None] = relationship(lazy="joined")
    inmueble: Mapped[Inmueble | None] = relationship(lazy="joined")
    tipo: Mapped[PolizaTipo] = relationship(lazy="joined")
    aseguradora: Mapped[Aseguradora] = relationship(lazy="joined")


class PolizaEvento(UUIDPrimaryKeyMixin, Base):
    """Every change to a policy or an insurer (G-087: «fecha, hora y quién lo hizo»)."""

    __tablename__ = "poliza_eventos"

    poliza_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("polizas.id", ondelete="CASCADE"), index=True
    )
    aseguradora_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("aseguradoras.id", ondelete="CASCADE"), index=True
    )
    registro: Mapped[str] = mapped_column(String(200))  # «NEG-0143 · Entidad 1», «Entidad 4»
    accion: Mapped[str] = mapped_column(String(200))
    antes: Mapped[str | None] = mapped_column(String(300))
    despues: Mapped[str | None] = mapped_column(String(300))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False, index=True
    )

    actor: Mapped[User | None] = relationship(lazy="joined")
