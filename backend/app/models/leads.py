import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Identity, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum
from app.models.enums import (
    CITA_ACTIVA,
    AccionSeguimiento,
    EstadoCita,
    EtapaLead,
    FuenteLead,
    MotivoPerdida,
    TipoCita,
    TipoEventoLead,
    TipoNegocio,
)
from app.models.user import User


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (Index("ix_leads_etapa_assigned", "etapa", "assigned_to_id"),)

    numero: Mapped[int] = mapped_column(Identity(start=1101), unique=True)

    # Cliente
    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(320))

    # Qué busca
    fuente: Mapped[FuenteLead] = mapped_column(pg_enum(FuenteLead, "fuente_lead"))
    fuente_detalle: Mapped[str | None] = mapped_column(String(200))  # «anuncio», campaña…
    negocio: Mapped[TipoNegocio | None] = mapped_column(pg_enum(TipoNegocio, "tipo_negocio"))
    busca: Mapped[str | None] = mapped_column(String(200))  # «Apartamento en Laureles»
    presupuesto: Mapped[str | None] = mapped_column(String(100))
    zona: Mapped[str | None] = mapped_column(String(200))
    para_cuando: Mapped[str | None] = mapped_column(String(100))
    notas: Mapped[str | None] = mapped_column(Text)

    # Proceso
    etapa: Mapped[EtapaLead] = mapped_column(
        pg_enum(EtapaLead, "etapa_lead"), default=EtapaLead.NUEVO, server_default="nuevo"
    )
    motivo_perdida: Mapped[MotivoPerdida | None] = mapped_column(
        pg_enum(MotivoPerdida, "motivo_perdida")
    )
    perdida_descuenta: Mapped[bool | None]
    cerrado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )  # null = llegó solo (integración)

    assigned_to: Mapped[User | None] = relationship(foreign_keys=[assigned_to_id], lazy="joined")
    seguimientos: Mapped[list["Seguimiento"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Seguimiento.due_at",
    )
    citas: Mapped[list["Cita"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Cita.scheduled_at",
    )

    @property
    def code(self) -> str:
        return f"LD-{self.numero:04d}"

    @property
    def is_closed(self) -> bool:
        return self.etapa in (EtapaLead.GANADO, EtapaLead.PERDIDO)

    @property
    def proximo_seguimiento(self) -> "Seguimiento | None":
        return next((s for s in self.seguimientos if s.done_at is None), None)

    @property
    def cita_activa(self) -> "Cita | None":
        return next((c for c in self.citas if c.estado in CITA_ACTIVA), None)


class LeadEvento(UUIDPrimaryKeyMixin, Base):
    """One line of the lead's chronological history (conversation, calls, stage changes…)."""

    __tablename__ = "lead_eventos"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[TipoEventoLead] = mapped_column(pg_enum(TipoEventoLead, "tipo_evento_lead"))
    titulo: Mapped[str] = mapped_column(String(200))
    detalle: Mapped[str | None] = mapped_column(Text)
    datos: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    cita_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("citas.id", ondelete="SET NULL"), index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # clock_timestamp(): several events written in one request keep their order.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )

    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="joined")

    @property
    def created_by_name(self) -> str | None:
        return self.created_by.full_name if self.created_by else None


class Seguimiento(UUIDPrimaryKeyMixin, Base):
    """A future action on a lead («Seguimiento del cliente»), marked done when it happens."""

    __tablename__ = "lead_seguimientos"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True
    )
    accion: Mapped[AccionSeguimiento] = mapped_column(
        pg_enum(AccionSeguimiento, "accion_seguimiento")
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    nota: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    done_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resultado: Mapped[str | None] = mapped_column(Text)

    lead: Mapped[Lead] = relationship(back_populates="seguimientos")


class Cita(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "citas"

    numero: Mapped[int] = mapped_column(Identity(start=401), unique=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[TipoCita] = mapped_column(pg_enum(TipoCita, "tipo_cita"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    asesor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    estado: Mapped[EstadoCita] = mapped_column(
        pg_enum(EstadoCita, "estado_cita"), default=EstadoCita.PENDIENTE, server_default="pendiente"
    )
    inmueble: Mapped[str | None] = mapped_column(String(200))  # free text until Inmuebles exists
    notas: Mapped[str | None] = mapped_column(Text)
    motivo: Mapped[str | None] = mapped_column(Text)  # last rejection / cancellation reason
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    lead: Mapped[Lead] = relationship(back_populates="citas", lazy="joined")
    asesor: Mapped[User | None] = relationship(foreign_keys=[asesor_id], lazy="joined")

    @property
    def code(self) -> str:
        return f"CIT-{self.numero:04d}"

    @property
    def asesor_name(self) -> str | None:
        return self.asesor.full_name if self.asesor else None
