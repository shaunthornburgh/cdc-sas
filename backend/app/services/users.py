"""User management with the business rules applied.

Every function takes an optional `actor` (the logged-in user making the change).
Scripts such as the seed pass no actor and skip the actor checks.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import ActividadEvento, User, UserActividad
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


def update_user(db: Session, user: User, changes: Mapping[str, Any], *, actor: User | None) -> User:
    """Apply a partial update. Allowed keys: full_name, cargo, is_active, funcion."""
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

    if "full_name" in changes:
        user.full_name = changes["full_name"]
    if "is_active" in changes:
        user.is_active = changes["is_active"]
    user.cargo = new_cargo
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
