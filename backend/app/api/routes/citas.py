import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DbSession
from app.api.permissions import require_leads_module
from app.models import Cita, User
from app.models.enums import TipoCita
from app.schemas.leads import (
    AsesorOption,
    CitaCreate,
    CitaEstadoIn,
    CitaEventoRead,
    CitaList,
    CitaRead,
    CitaReasignar,
    CitaReprogramar,
    CitaUpdate,
    OcupadoRef,
)
from app.services import citas as service
from app.services import fechas
from app.services import leads as lead_service

router = APIRouter(prefix="/citas", tags=["citas"])

# Control de citas is part of the Atención al Cliente / Pre-ventas module.
Handler = Annotated[User, Depends(require_leads_module)]


def _read(cita: Cita, historial: list, now) -> CitaRead:
    return CitaRead.model_validate(
        {
            **{f: getattr(cita, f) for f in CitaRead.model_fields if hasattr(cita, f)},
            "requiere_accion": service.requiere_accion(cita, now),
            "bucket": service.bucket(cita, now),
            "historial": [CitaEventoRead.model_validate(e) for e in historial],
        }
    )


def _one(db, cita: Cita) -> CitaRead:
    db.refresh(cita)
    return _read(cita, service.historial(db, [cita])[cita.id], fechas.now())


@router.get("", response_model=CitaList)
def list_citas(
    db: DbSession,
    _: Handler,
    bucket: Annotated[
        str | None, Query(description="accion | pendientes | aceptadas | realizadas | canceladas")
    ] = None,
    lead_id: uuid.UUID | None = None,
    asesor_id: uuid.UUID | None = None,
    desde: date | None = None,
    hasta: date | None = None,
) -> CitaList:
    rows, counts = service.list_citas(
        db,
        service.CitaFilters(
            bucket=bucket, lead_id=lead_id, asesor_id=asesor_id, desde=desde, hasta=hasta
        ),
    )
    hist = service.historial(db, rows)
    now = fechas.now()
    return CitaList(items=[_read(c, hist[c.id], now) for c in rows], counts=counts)


@router.get("/asesores", response_model=list[AsesorOption])
def asesores(
    db: DbSession,
    _: Handler,
    tipo: TipoCita,
    scheduled_at: Annotated[str | None, Query(description="ISO 8601 con zona horaria")] = None,
    exclude: uuid.UUID | None = None,
) -> list[AsesorOption]:
    """Asesores for a cita type: who has the activity and who is free at that time."""
    from pydantic import AwareDatetime, TypeAdapter

    at = TypeAdapter(AwareDatetime).validate_python(scheduled_at) if scheduled_at else None
    return [
        AsesorOption(
            id=a.user.id,
            full_name=a.user.full_name,
            actividades=a.user.actividades,
            elegible=a.elegible,
            ocupado_con=OcupadoRef.model_validate(a.ocupado_con) if a.ocupado_con else None,
        )
        for a in service.asesores(db, tipo, at, exclude)
    ]


@router.post("", response_model=CitaRead, status_code=status.HTTP_201_CREATED)
def create_cita(body: CitaCreate, db: DbSession, user: Handler) -> CitaRead:
    lead = lead_service.get_lead(db, user, body.lead_id)
    cita = service.create_cita(
        db,
        lead,
        tipo=body.tipo,
        scheduled_at=body.scheduled_at,
        asesor_id=body.asesor_id,
        inmueble=body.inmueble,
        notas=body.notas,
        actor=user,
    )
    db.commit()
    return _one(db, cita)


@router.get("/{cita_id}", response_model=CitaRead)
def get_cita(cita_id: uuid.UUID, db: DbSession, _: Handler) -> CitaRead:
    return _one(db, service.get_cita(db, cita_id))


@router.patch("/{cita_id}", response_model=CitaRead)
def update_cita(cita_id: uuid.UUID, body: CitaUpdate, db: DbSession, user: Handler) -> CitaRead:
    cita = service.get_cita(db, cita_id)
    service.update_detalles(db, cita, inmueble=body.inmueble, notas=body.notas, actor=user)
    db.commit()
    return _one(db, cita)


@router.post("/{cita_id}/status", response_model=CitaRead)
def set_status(cita_id: uuid.UUID, body: CitaEstadoIn, db: DbSession, user: Handler) -> CitaRead:
    """Record the asesor's answer (aceptada / rechazada), or mark realizada / cancelada."""
    cita = service.get_cita(db, cita_id)
    service.set_estado(db, cita, body.estado, motivo=body.motivo, actor=user)
    db.commit()
    return _one(db, cita)


@router.post("/{cita_id}/reassign", response_model=CitaRead)
def reassign(cita_id: uuid.UUID, body: CitaReasignar, db: DbSession, user: Handler) -> CitaRead:
    cita = service.get_cita(db, cita_id)
    service.reasignar(db, cita, body.asesor_id, actor=user)
    db.commit()
    return _one(db, cita)


@router.post("/{cita_id}/reschedule", response_model=CitaRead)
def reschedule(cita_id: uuid.UUID, body: CitaReprogramar, db: DbSession, user: Handler) -> CitaRead:
    cita = service.get_cita(db, cita_id)
    service.reprogramar(db, cita, body.scheduled_at, motivo=body.motivo, actor=user)
    db.commit()
    return _one(db, cita)
