import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DbSession
from app.api.permissions import USER_MANAGERS, require_cargo
from app.models import ActividadEvento, User
from app.models.enums import Cargo
from app.schemas.user import (
    ActividadesUpdate,
    ActividadEventoRead,
    FuncionUpdate,
    UserCambioRead,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.services import users as service

router = APIRouter(prefix="/users", tags=["users"])

# Only Gerencia and Coordinación reach any route below.
Manager = Annotated[User, Depends(require_cargo(*USER_MANAGERS))]


def _get_or_404(db: DbSession, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado.")
    return user


@router.get("", response_model=list[UserRead])
def list_users(
    db: DbSession,
    _: Manager,
    q: Annotated[str | None, Query(max_length=100, description="Busca en nombre o correo")] = None,
    cargo: Cargo | None = None,
    is_active: bool | None = None,
) -> list[User]:
    return service.list_users(db, q=q, cargo=cargo, is_active=is_active)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, db: DbSession, actor: Manager) -> User:
    user = service.create_user(db, **body.model_dump(), actor=actor)
    db.commit()
    return user


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: uuid.UUID, db: DbSession, _: Manager) -> User:
    return _get_or_404(db, user_id)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: uuid.UUID, body: UserUpdate, db: DbSession, actor: Manager) -> User:
    user = _get_or_404(db, user_id)
    service.update_user(db, user, body.model_dump(exclude_unset=True), actor=actor)
    db.commit()
    return user


@router.post("/{user_id}/activities", response_model=UserRead)
def set_activities(
    user_id: uuid.UUID, body: ActividadesUpdate, db: DbSession, actor: Manager
) -> User:
    """Replace the user's commercial activities with exactly this list."""
    user = _get_or_404(db, user_id)
    service.set_actividades(db, user, body.actividades, actor=actor)
    db.commit()
    return user


@router.get("/{user_id}/activities/history", response_model=list[ActividadEventoRead])
def activity_history(user_id: uuid.UUID, db: DbSession, _: Manager) -> list[ActividadEvento]:
    return service.activity_history(db, _get_or_404(db, user_id))


@router.get("/{user_id}/cambios", response_model=list[UserCambioRead])
def cambios(user_id: uuid.UUID, db: DbSession, _: Manager) -> list[dict]:
    """Personal data changes: field, before and after, who and when."""
    return [
        {
            "campo": c.campo,
            "campo_txt": service.CAMPO_LABELS.get(c.campo, c.campo),
            "antes": c.antes,
            "despues": c.despues,
            "actor_name": c.actor.full_name if c.actor else None,
            "created_at": c.created_at,
        }
        for c in service.cambios(db, _get_or_404(db, user_id))
    ]


@router.post("/{user_id}/funcion", response_model=UserRead)
def set_funcion(user_id: uuid.UUID, body: FuncionUpdate, db: DbSession, actor: Manager) -> User:
    """Set or clear (null) the independent function: Atención al Cliente / Pre-ventas."""
    user = _get_or_404(db, user_id)
    service.set_funcion(db, user, body.funcion, actor=actor)
    db.commit()
    return user
