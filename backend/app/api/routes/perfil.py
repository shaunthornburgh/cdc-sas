from typing import Any

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.perfil import Foto, PasswordIn, Perfil
from app.services import perfil as svc

# Z01 / M11 «Mi perfil»: the signed-in person, about themselves.
router = APIRouter(prefix="/perfil", tags=["perfil"])


@router.get("", response_model=Perfil)
def ver(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return svc.perfil(db, user)


@router.get("/foto", response_model=Foto)
def foto(user: CurrentUser) -> dict[str, Any]:
    """The photo apart (it can be large): the sidebar and the profile load it on demand."""
    return {"foto": user.foto}


@router.put("/foto", response_model=Foto)
def cambiar_foto(body: Foto, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    svc.cambiar_foto(db, user, body.foto)
    db.commit()
    return {"foto": user.foto}


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def cambiar_password(body: PasswordIn, db: DbSession, user: CurrentUser) -> None:
    svc.cambiar_password(db, user, body.actual, body.nueva)
    db.commit()


@router.post("/politica", response_model=Perfil)
def aceptar_politica(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    svc.aceptar_politica(db, user)
    db.commit()
    return svc.perfil(db, user)
