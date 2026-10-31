import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.models import User
from app.schemas.asesor import AsesorCita, AsesorInicio, CierreIn, MisCitas, RechazoIn
from app.services import asesor as service
from app.services import citas as cita_service
from app.services import fechas
from app.services.policies import can_use_asesor_home, has_commercial_activity, is_manager

router = APIRouter(prefix="/asesor", tags=["asesor"])


def require_asesor_home(user: CurrentUser) -> User:
    """Asesores (Captación, Ventas or Arriendos). Coordinación / Gerencia may look at one."""
    if not can_use_asesor_home(user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Esta pantalla es para asesores comerciales."
        )
    return user


def require_asesor(user: CurrentUser) -> User:
    """Only the asesor answers their own citas."""
    if not has_commercial_activity(user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Solo un asesor comercial responde sus citas."
        )
    return user


Viewer = Annotated[User, Depends(require_asesor_home)]
Asesor = Annotated[User, Depends(require_asesor)]


def _target(db: DbSession, user: User, asesor_id: uuid.UUID | None) -> User:
    if asesor_id is None or asesor_id == user.id:
        if not has_commercial_activity(user):
            raise HTTPException(422, "Elige el asesor que quieres ver (asesor_id).")
        return user
    if not is_manager(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo ves tu propia pantalla.")
    target = db.get(User, asesor_id)
    if target is None or not has_commercial_activity(target):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asesor no encontrado.")
    return target


@router.get("/inicio", response_model=AsesorInicio)
def inicio(db: DbSession, user: Viewer, asesor_id: uuid.UUID | None = None) -> dict:
    """M01 / M02: pending items, today's citas, captaciones and this month's results."""
    return service.inicio(db, _target(db, user, asesor_id))


@router.get("/citas", response_model=MisCitas)
def citas(db: DbSession, user: Viewer, asesor_id: uuid.UUID | None = None) -> dict:
    """M03: to answer (incl. rejected ones the asesor can take), upcoming, to close, closed."""
    lists, counts = service.mis_citas(db, _target(db, user, asesor_id))
    return {**lists, "counts": counts}


def _one(db, cita, asesor: User) -> dict:
    db.refresh(cita)
    now: datetime = fechas.now()
    return service.cita_item(cita, asesor, db, now, service._creator_names(db, [cita]))


@router.post("/citas/{cita_id}/aceptar", response_model=AsesorCita)
def aceptar(cita_id: uuid.UUID, db: DbSession, user: Asesor) -> dict:
    cita = cita_service.get_cita(db, cita_id)
    cita_service.aceptar_por_asesor(db, cita, asesor=user)
    db.commit()
    return _one(db, cita, user)


@router.post("/citas/{cita_id}/rechazar", response_model=AsesorCita)
def rechazar(cita_id: uuid.UUID, body: RechazoIn, db: DbSession, user: Asesor) -> dict:
    cita = cita_service.get_cita(db, cita_id)
    cita_service.rechazar_por_asesor(
        db, cita, motivo=body.motivo, observacion=body.observacion, asesor=user
    )
    db.commit()
    return _one(db, cita, user)


@router.post("/citas/{cita_id}/tomar", response_model=AsesorCita)
def tomar(cita_id: uuid.UUID, db: DbSession, user: Asesor) -> dict:
    """«Tomar cita»: a cita another asesor rejected; the first one to take it keeps it."""
    cita = cita_service.get_cita(db, cita_id)
    cita_service.tomar(db, cita, asesor=user)
    db.commit()
    return _one(db, cita, user)


@router.post("/citas/{cita_id}/cerrar", response_model=AsesorCita)
def cerrar(cita_id: uuid.UUID, body: CierreIn, db: DbSession, user: Asesor) -> dict:
    cita = cita_service.get_cita(db, cita_id)
    cita_service.cerrar_por_asesor(db, cita, resultado=body.resultado, asesor=user)
    db.commit()
    return _one(db, cita, user)
