import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.api.permissions import USER_MANAGERS, require_cargo, require_leads_module
from app.models import Lead, User
from app.models.enums import EtapaLead, FuenteLead, TipoEventoLead
from app.schemas.leads import (
    AccionIn,
    CitaRef,
    EventoRead,
    LeadCreate,
    LeadDetail,
    LeadStats,
    LeadSummary,
    LeadUpdate,
    LlamadaIn,
    MensajeIn,
    SeguimientoComplete,
    SeguimientoCreate,
    SeguimientoRead,
    StageChange,
    UserRef,
)
from app.services import citas as cita_service
from app.services import leads as service
from app.services.policies import can_use_leads

router = APIRouter(prefix="/leads", tags=["leads"])

# Atención al Cliente / Pre-ventas, Coordinación and Gerencia.
Handler = Annotated[User, Depends(require_leads_module)]
Manager = Annotated[User, Depends(require_cargo(*USER_MANAGERS))]


def _cita_ref(c) -> CitaRef:
    return CitaRef.model_validate(c).model_copy(
        update={"requiere_accion": cita_service.requiere_accion(c)}
    )


def _summary(lead: Lead, extras: service.LeadExtras, user: User) -> dict:
    return {
        **LeadSummary.model_validate(
            {
                **{f: getattr(lead, f) for f in LeadSummary.model_fields if hasattr(lead, f)},
                "llamadas": extras.llamadas,
                "ultimo_evento": extras.ultimo_evento,
                "can_edit": service.can_edit(user, lead),
                "proximo_seguimiento": lead.proximo_seguimiento,
                "cita_activa": None,
            }
        ).model_dump(),
        "cita_activa": _cita_ref(lead.cita_activa) if lead.cita_activa else None,
    }


def _detail(db, lead: Lead, user: User) -> LeadDetail:
    db.refresh(lead)
    extras = service.extras_for(db, [lead])[lead.id]
    stats = service.call_stats(db, lead)
    return LeadDetail.model_validate(
        {
            **_summary(lead, extras, user),
            "presupuesto": lead.presupuesto,
            "zona": lead.zona,
            "para_cuando": lead.para_cuando,
            "notas": lead.notas,
            "llamadas_dias_seguidos": stats.dias_seguidos,
            "eventos": [EventoRead.model_validate(e) for e in service.eventos(db, lead)],
            "seguimientos": [SeguimientoRead.model_validate(s) for s in lead.seguimientos],
            "citas": [_cita_ref(c) for c in lead.citas],
        }
    )


@router.get("", response_model=list[LeadSummary])
def list_leads(
    db: DbSession,
    user: Handler,
    etapa: Annotated[list[EtapaLead] | None, Query()] = None,
    abiertos: bool | None = None,
    assigned: Annotated[str | None, Query(description="me | none | id de usuario")] = None,
    fuente: FuenteLead | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> list[dict]:
    """Atención / Pre-ventas get unassigned leads and their own; managers get all."""
    filters = service.LeadFilters(
        etapas=tuple(etapa or ()),
        abiertos=abiertos,
        assigned=assigned,
        fuente=fuente,
        desde=desde,
        hasta=hasta,
        q=q,
    )
    leads = service.list_leads(db, user, filters)
    extras = service.extras_for(db, leads)
    return [_summary(lead, extras[lead.id], user) for lead in leads]


@router.get("/stats", response_model=LeadStats)
def lead_stats(
    db: DbSession,
    user: Handler,
    periodo: Annotated[str, Query(pattern="^(hoy|semana|mes)$")] = "mes",
) -> dict:
    return service.stats(db, user, periodo)


@router.get("/responsables", response_model=list[UserRef])
def responsables(db: DbSession, _: Manager) -> list[User]:
    """People a lead can be (re)assigned to."""
    users = db.scalars(select(User).where(User.is_active).order_by(User.full_name)).unique()
    return [u for u in users if can_use_leads(u)]


@router.post("", response_model=LeadDetail, status_code=status.HTTP_201_CREATED)
def create_lead(body: LeadCreate, db: DbSession, user: Handler) -> LeadDetail:
    data = body.model_dump(exclude={"seguir"})
    lead = service.create_lead(db, data, actor=user, seguir=body.seguir)
    db.commit()
    return _detail(db, lead, user)


@router.get("/{lead_id}", response_model=LeadDetail)
def get_lead(lead_id: uuid.UUID, db: DbSession, user: Handler) -> LeadDetail:
    return _detail(db, service.get_lead(db, user, lead_id), user)


@router.patch("/{lead_id}", response_model=LeadDetail)
def update_lead(lead_id: uuid.UUID, body: LeadUpdate, db: DbSession, user: Handler) -> LeadDetail:
    lead = service.get_lead(db, user, lead_id)
    service.update_lead(db, lead, body.model_dump(exclude_unset=True), actor=user)
    db.commit()
    return _detail(db, lead, user)


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(lead_id: uuid.UUID, db: DbSession, user: Handler) -> Response:
    service.delete_lead(db, service.get_lead(db, user, lead_id), actor=user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{lead_id}/follow", response_model=LeadDetail)
def follow_lead(lead_id: uuid.UUID, db: DbSession, user: Handler) -> LeadDetail:
    """«Seguir lead»: become the only person responsible for it."""
    lead = service.get_lead(db, user, lead_id)
    service.follow_lead(db, lead, user)
    db.commit()
    return _detail(db, lead, user)


@router.post("/{lead_id}/actions", response_model=LeadDetail)
def register_action(lead_id: uuid.UUID, body: AccionIn, db: DbSession, user: Handler) -> LeadDetail:
    """Log a call, a message, options sent or an observation."""
    lead = service.get_lead(db, user, lead_id)
    if isinstance(body, LlamadaIn):
        service.registrar_llamada(
            db,
            lead,
            resultado=body.resultado,
            resumen=body.resumen,
            duracion_min=body.duracion_min,
            actor=user,
        )
    elif isinstance(body, MensajeIn):
        tipo = TipoEventoLead.MENSAJE if body.tipo == "mensaje" else TipoEventoLead.OPCIONES
        service.registrar_mensaje(
            db,
            lead,
            tipo=tipo,
            medio=body.medio,
            texto=body.texto,
            actor=user,
            inmueble_ids=body.inmueble_ids if tipo == TipoEventoLead.OPCIONES else [],
        )
    else:
        service.registrar_observacion(db, lead, texto=body.texto, actor=user)
    db.commit()
    return _detail(db, lead, user)


@router.post("/{lead_id}/followups", response_model=LeadDetail, status_code=status.HTTP_201_CREATED)
def create_followup(
    lead_id: uuid.UUID, body: SeguimientoCreate, db: DbSession, user: Handler
) -> LeadDetail:
    lead = service.get_lead(db, user, lead_id)
    service.programar_seguimiento(
        db, lead, accion=body.accion, due_at=body.due_at, nota=body.nota, actor=user
    )
    db.commit()
    return _detail(db, lead, user)


@router.post("/{lead_id}/followups/{seguimiento_id}/complete", response_model=LeadDetail)
def complete_followup(
    lead_id: uuid.UUID,
    seguimiento_id: uuid.UUID,
    body: SeguimientoComplete,
    db: DbSession,
    user: Handler,
) -> LeadDetail:
    lead = service.get_lead(db, user, lead_id)
    service.completar_seguimiento(db, lead, seguimiento_id, resultado=body.resultado, actor=user)
    db.commit()
    return _detail(db, lead, user)


@router.post("/{lead_id}/stage", response_model=LeadDetail)
def change_stage(lead_id: uuid.UUID, body: StageChange, db: DbSession, user: Handler) -> LeadDetail:
    """Move the lead to another stage. «Perdido» needs a reason; «Ganado» is for managers."""
    lead = service.get_lead(db, user, lead_id)
    service.change_stage(db, lead, body.etapa, motivo=body.motivo, actor=user)
    db.commit()
    return _detail(db, lead, user)
