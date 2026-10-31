import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum
from app.models.enums import ActividadComercial, Cargo, FuncionIndependiente


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        # The Atención al Cliente cargo always carries the matching independent function.
        CheckConstraint(
            "cargo <> 'atencion_cliente' OR (funcion IS NOT NULL AND funcion = 'atencion_cliente')",
            name="atencion_cliente_funcion",
        ),
    )

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    cargo: Mapped[Cargo] = mapped_column(pg_enum(Cargo, "cargo"))
    # Atención al Cliente / Pre-ventas. Mutually exclusive with commercial activities
    # (enforced in app.services.users and by a DB trigger).
    funcion: Mapped[FuncionIndependiente | None] = mapped_column(
        pg_enum(FuncionIndependiente, "funcion_independiente")
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

    actividad_links: Mapped[list["UserActividad"]] = relationship(
        back_populates="user",
        foreign_keys="UserActividad.user_id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @validates("email")
    def _normalise_email(self, _key: str, value: str) -> str:
        return value.strip().lower()

    @property
    def actividades(self) -> list[ActividadComercial]:
        # Stable order, as declared in the enum.
        return [a for a in ActividadComercial if self.has_actividad(a)]

    def has_actividad(self, actividad: ActividadComercial) -> bool:
        return any(link.actividad == actividad for link in self.actividad_links)

    @property
    def gps_checkin_enabled(self) -> bool:
        """GPS / check-in only applies when Captación is active."""
        return self.has_actividad(ActividadComercial.CAPTACION)

    def __repr__(self) -> str:
        return f"<User {self.email} {self.cargo}>"


class UserActividad(Base):
    """A commercial activity switched on for a user (row present = active)."""

    __tablename__ = "user_actividades"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    actividad: Mapped[ActividadComercial] = mapped_column(
        pg_enum(ActividadComercial, "actividad_comercial"), primary_key=True
    )
    granted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="actividad_links", foreign_keys=[user_id])


class ActividadEvento(UUIDPrimaryKeyMixin, Base):
    """History of activities being switched on (activada=True) or off (activada=False)."""

    __tablename__ = "actividad_eventos"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    actividad: Mapped[ActividadComercial] = mapped_column(
        pg_enum(ActividadComercial, "actividad_comercial")
    )
    activada: Mapped[bool]
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # clock_timestamp(), not now(): several events saved in one transaction keep their order.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )

    changed_by: Mapped[User | None] = relationship(foreign_keys=[changed_by_id], lazy="joined")

    @property
    def changed_by_name(self) -> str | None:
        return self.changed_by.full_name if self.changed_by else None
