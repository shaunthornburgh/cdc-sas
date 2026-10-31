import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum
from app.models.enums import (
    EstadoPedido,
    MotivoPerdidaPedido,
    TipoEventoPedido,
    TipoInmueble,
    TipoNegocio,
    UrgenciaPedido,
)
from app.models.user import User


class Pedido(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """What a client is looking for (venta / arriendo), with a deadline and one responsable."""

    __tablename__ = "pedidos"
    __table_args__ = (Index("ix_pedidos_estado_responsable", "estado", "responsable_id"),)

    numero: Mapped[int] = mapped_column(Identity(start=30), unique=True)

    # Cliente
    cliente_nombre: Mapped[str] = mapped_column(String(200))
    cliente_telefono: Mapped[str | None] = mapped_column(String(40))
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("leads.id", ondelete="SET NULL"), index=True
    )

    # Qué busca
    negocio: Mapped[TipoNegocio] = mapped_column(
        pg_enum(TipoNegocio, "tipo_negocio", create_type=False)
    )
    tipo_inmueble: Mapped[TipoInmueble] = mapped_column(
        pg_enum(TipoInmueble, "tipo_inmueble", create_type=False)
    )
    zona: Mapped[str] = mapped_column(String(80))
    presupuesto: Mapped[int] = mapped_column(BigInteger)  # COP: price (venta) or monthly rent
    observaciones: Mapped[str | None] = mapped_column(Text)
    fecha_limite: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    urgencia: Mapped[UrgenciaPedido] = mapped_column(
        pg_enum(UrgenciaPedido, "urgencia_pedido"),
        default=UrgenciaPedido.NORMAL,
        server_default="normal",
    )

    # Proceso
    estado: Mapped[EstadoPedido] = mapped_column(
        pg_enum(EstadoPedido, "estado_pedido"),
        default=EstadoPedido.ABIERTO,
        server_default="abierto",
    )
    vencio: Mapped[bool] = mapped_column(
        default=False, server_default="false"
    )  # passed its deadline once
    motivo_perdida: Mapped[MotivoPerdidaPedido | None] = mapped_column(
        pg_enum(MotivoPerdidaPedido, "motivo_perdida_pedido")
    )
    cerrado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    responsable_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    responsable: Mapped[User] = relationship(foreign_keys=[responsable_id], lazy="joined")
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="joined")
    eventos: Mapped[list["PedidoEvento"]] = relationship(
        back_populates="pedido",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PedidoEvento.created_at",
    )

    @property
    def code(self) -> str:
        return f"PED-{self.numero:03d}"

    @property
    def created_by_name(self) -> str | None:
        return self.created_by.full_name if self.created_by else None


class PedidoEvento(UUIDPrimaryKeyMixin, Base):
    """History of a pedido: updates keep «antes / después», plus proposals and comments."""

    __tablename__ = "pedido_eventos"

    pedido_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pedidos.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[TipoEventoPedido] = mapped_column(pg_enum(TipoEventoPedido, "tipo_evento_pedido"))
    titulo: Mapped[str] = mapped_column(String(200))
    detalle: Mapped[str | None] = mapped_column(Text)
    datos: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )

    pedido: Mapped[Pedido] = relationship(back_populates="eventos")
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="joined")

    @property
    def created_by_name(self) -> str | None:
        return self.created_by.full_name if self.created_by else None
