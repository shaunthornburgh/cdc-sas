"""User management with the business rules applied.

Every function takes an optional `actor` (the logged-in user making the change).
Scripts such as the seed pass no actor and skip the actor checks.
"""

import re
from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import ActividadEvento, User, UserActividad, UserCambio
from app.models.enums import ActividadComercial, Cargo, FuncionIndependiente
from app.services.errors import ConflictError, DomainError, PermissionDeniedError

__all__ = ["ConflictError", "DomainError", "PermissionDeniedError"]


# ---------------------------------------------------------------- rules


def validate_profile(
    cargo: Cargo,
    funcion: FuncionIndependiente | None,
    actividades: Iterable[ActividadComercial],
) -> None:
    if cargo == Cargo.ATENCION_CLIENTE and funcion != FuncionIndependiente.ATENCION_CLIENTE:
        raise DomainError("El cargo Atención al Cliente requiere la función Atención al Cliente.")
    if funcion is not None and set(actividades):
        raise DomainError(
            "Atención al Cliente y Pre-ventas no se pueden combinar con actividades comerciales."
        )


def ensure_can_manage(actor: User | None, target: User | None, new_cargo: Cargo | None) -> None:
    """Only Gerencia can create, edit or promote to Gerencia users."""
    if actor is None or actor.cargo == Cargo.GERENCIA:
        return
    if (target is not None and target.cargo == Cargo.GERENCIA) or new_cargo == Cargo.GERENCIA:
        raise PermissionDeniedError("Solo Gerencia puede crear o modificar usuarios de Gerencia.")


# ---------------------------------------------------------------- queries


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def list_users(
    db: Session,
    *,
    q: str | None = None,
    cargo: Cargo | None = None,
    is_active: bool | None = None,
) -> list[User]:
    stmt = select(User).order_by(User.full_name, User.email)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(User.full_name.ilike(like) | User.email.ilike(like))
    if cargo is not None:
        stmt = stmt.where(User.cargo == cargo)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    return list(db.scalars(stmt))


def activity_history(db: Session, user: User, limit: int = 50) -> list[ActividadEvento]:
    stmt = (
        select(ActividadEvento)
        .where(ActividadEvento.user_id == user.id)
        .order_by(ActividadEvento.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


# ---------------------------------------------------------------- commands


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    cargo: Cargo,
    funcion: FuncionIndependiente | None = None,
    actividades: Iterable[ActividadComercial] = (),
    is_active: bool = True,
    actor: User | None = None,
) -> User:
    ensure_can_manage(actor, None, cargo)
    if cargo == Cargo.ATENCION_CLIENTE and funcion is None:
        funcion = FuncionIndependiente.ATENCION_CLIENTE
    actividades = set(actividades)
    validate_profile(cargo, funcion, actividades)
    if get_user_by_email(db, email):
        raise ConflictError(f"Ya existe un usuario con el correo {email.strip().lower()}.")

    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        cargo=cargo,
        funcion=funcion,
        is_active=is_active,
    )
    db.add(user)
    db.flush()  # assigns user.id for the activity rows
    _apply_actividades(db, user, actividades, actor)
    return user


CAMPO_LABELS = {
    "full_name": "Nombre",
    "cargo": "Cargo",
    "is_active": "Estado",
    "telefono": "Teléfono",
    "documento": "Cédula",
    "fecha_ingreso": "Fecha de ingreso",
    "foto": "Foto",
    "password": "Contraseña",
}
_TELEFONO = re.compile(r"^[0-9+()\- ]{7,40}$")
_DOCUMENTO = re.compile(r"^[0-9A-Za-z.\-]{5,30}$")


def _txt(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return "Activo" if v else "Inactivo"
    if isinstance(v, date):
        return v.isoformat()
    if hasattr(v, "value"):
        return str(v.value)
    return str(v)[:300]


def log_cambio(db: Session, user: User, campo: str, antes: Any, despues: Any, actor: User | None):
    """Personal data changes keep the value before and after (documents are stored masked)."""
    if campo == "documento":
        antes, despues = mask(antes), mask(despues)
    if campo == "foto":
        antes = "con foto" if antes else "sin foto"
        despues = "con foto" if despues else "sin foto"
    db.add(
        UserCambio(
            user_id=user.id,
            campo=campo,
            antes=_txt(antes),
            despues=_txt(despues),
            actor_id=actor.id if actor else None,
        )
    )


def mask(documento: str | None) -> str | None:
    """«••••••2210»: only the last 4 characters (Z01)."""
    if not documento:
        return None
    limpio = re.sub(r"[^0-9A-Za-z]", "", documento)  # «1.020.454.521» → last 4 = 4521
    return "••••••" + limpio[-4:]


def cambios(db: Session, user: User, limit: int = 30) -> list[UserCambio]:
    return list(
        db.scalars(
            select(UserCambio)
            .where(UserCambio.user_id == user.id)
            .order_by(UserCambio.created_at.desc())
            .limit(limit)
        ).unique()
    )


def _datos(changes: Mapping[str, Any]) -> dict[str, Any]:
    """Validate telefono, documento and fecha_ingreso (empty = clear)."""
    out: dict[str, Any] = {}
    if "telefono" in changes:
        t = (changes["telefono"] or "").strip() or None
        if t and not _TELEFONO.match(t):
            raise DomainError("Revisa el teléfono: solo números, espacios, + y guiones.")
        out["telefono"] = t
    if "documento" in changes:
        d = (changes["documento"] or "").replace(" ", "") or None
        if d and not _DOCUMENTO.match(d):
            raise DomainError("Revisa la cédula: entre 5 y 30 números o letras.")
        out["documento"] = d
    if "fecha_ingreso" in changes:
        f = changes["fecha_ingreso"]
        if f is not None and f > date.today():
            raise DomainError("La fecha de ingreso no puede ser futura.")
        out["fecha_ingreso"] = f
    return out


def update_user(db: Session, user: User, changes: Mapping[str, Any], *, actor: User | None) -> User:
    """Apply a partial update. Allowed keys: full_name, cargo, is_active, funcion, telefono,
    documento, fecha_ingreso. Personal data changes are logged in `user_cambios`."""
    new_cargo: Cargo = changes.get("cargo", user.cargo)
    ensure_can_manage(actor, user, new_cargo)

    if actor is not None and actor.id == user.id:
        if new_cargo != user.cargo:
            raise PermissionDeniedError("No puedes cambiar tu propio cargo.")
        if changes.get("is_active") is False:
            raise PermissionDeniedError("No puedes desactivar tu propio usuario.")

    if "funcion" in changes:
        new_funcion = changes["funcion"]
    elif new_cargo == Cargo.ATENCION_CLIENTE and user.funcion is None:
        new_funcion = FuncionIndependiente.ATENCION_CLIENTE  # same default as create_user
    else:
        new_funcion = user.funcion
    validate_profile(new_cargo, new_funcion, user.actividades)

    nuevos = _datos(changes)
    if "full_name" in changes:
        nuevos["full_name"] = changes["full_name"]
    if "is_active" in changes:
        nuevos["is_active"] = changes["is_active"]
    nuevos["cargo"] = new_cargo
    for campo, valor in nuevos.items():
        if getattr(user, campo) != valor:
            log_cambio(db, user, campo, getattr(user, campo), valor, actor)
            setattr(user, campo, valor)
    user.funcion = new_funcion
    db.flush()
    return user


def set_funcion(
    db: Session, user: User, funcion: FuncionIndependiente | None, *, actor: User | None
) -> User:
    return update_user(db, user, {"funcion": funcion}, actor=actor)


def set_actividades(
    db: Session,
    user: User,
    actividades: Iterable[ActividadComercial],
    *,
    actor: User | None = None,
) -> User:
    """Replace the user's active commercial activities and log what changed and who did it."""
    ensure_can_manage(actor, user, None)
    wanted = set(actividades)
    validate_profile(user.cargo, user.funcion, wanted)
    _apply_actividades(db, user, wanted, actor)
    return user


def _apply_actividades(
    db: Session, user: User, wanted: set[ActividadComercial], actor: User | None
) -> None:
    current = set(user.actividades)
    added, removed = wanted - current, current - wanted
    if not added and not removed:
        return

    actor_id = actor.id if actor else None
    user.actividad_links = [link for link in user.actividad_links if link.actividad in wanted]
    for actividad in sorted(added):
        user.actividad_links.append(UserActividad(actividad=actividad, granted_by_id=actor_id))
    for actividad, activada in [*((a, True) for a in added), *((a, False) for a in removed)]:
        db.add(
            ActividadEvento(
                user_id=user.id, actividad=actividad, activada=activada, changed_by_id=actor_id
            )
        )
    db.flush()
