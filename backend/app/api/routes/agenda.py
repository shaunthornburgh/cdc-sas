import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.models import AgendaItem, User
from app.schemas.agenda import AgendaIn, Entrada, MotivoIn, Persona, Vista
from app.services import agenda as svc
from app.services import fechas
from app.services.errors import NotFoundError

# G09 (agenda) · M17 / C07 / X06 «Mi agenda» · K19 «Agenda» (decisions G-088, G-089).
router = APIRouter(prefix="/agenda", tags=["agenda"])


def _persona(viewer: User, u: User) -> dict[str, Any]:
    return {
        "id": u.id,
        "full_name": u.full_name,
        "rol_txt": svc.ROL_TXT.get(svc.rol(u) or "", ""),
        "yo": u.id == viewer.id,
        "puede_agregar": svc.puede_agregar(viewer, u),
    }


def _manual(viewer: User, it: AgendaItem, now: datetime) -> dict[str, Any]:
    est = svc.estado_de(it, now)
    txt, cls = svc.ESTADO[est]
    propia = it.creado_por_id == it.user_id
    por = it.creado_por.full_name if it.creado_por else None
    if propia:
        sub = "La agregaste tú" if it.creado_por_id == viewer.id else f"La agregó {por}"
    else:
        quien = (
            "ti"
            if it.creado_por_id == viewer.id
            else f"{por} ({svc.ROL_TXT.get(svc.rol(it.creado_por) or '', '')})"
        )
        sub = f"Asignada por {quien}"
    if it.prioridad == "alta":
        sub += " · prioridad alta"
    return {
        "id": str(it.id),
        "k": "man",
        "tipo": "mia" if propia else "asg",
        "fecha": it.fecha,
        "hora": it.hora,
        "hora_txt": svc.hora_txt(it.hora),
        "titulo": it.titulo,
        "sub": sub,
        "nota": it.nota,
        "prioridad": it.prioridad,
        "estado": est,
        "estado_txt": txt,
        "estado_cls": cls,
        "por_name": por,
        "por_yo": it.creado_por_id == viewer.id,
        "created_at": it.created_at,
        "motivo": it.motivo,
        "respondida_at": it.respondida_at,
        "aviso_titulo": it.aviso.titulo if it.aviso else None,
        "acciones": svc.acciones(viewer, it),
    }


def _sys(x: dict[str, Any]) -> dict[str, Any]:
    return x | {"hora_txt": svc.hora_txt(x["hora"])}


@router.get("/personas", response_model=list[Persona])
def personas(db: DbSession, user: CurrentUser) -> list[dict[str, Any]]:
    """«Agenda de [persona]»: yours first, then the ones you can see (G-088)."""
    return [_persona(user, u) for u in svc.personas(db, user)]


@router.get("", response_model=Vista)
def vista(
    db: DbSession,
    user: CurrentUser,
    user_id: uuid.UUID | None = None,
    desde: date | None = None,
    hasta: date | None = None,
) -> dict[str, Any]:
    target = svc.get_target(db, user, user_id)
    d1, d2 = svc.rango(desde, hasta)
    now = fechas.now()
    items = [_manual(user, it, now) for it in svc.manuales(db, target, d1, d2)]
    items += [_sys(x) for x in svc.sistema(db, user, target, d1, d2)]
    items.sort(key=lambda x: (x["fecha"], x["hora"] is None, x["hora"] or datetime.min.time()))
    return {
        "persona": _persona(user, target),
        "desde": d1,
        "hasta": d2,
        "items": items,
        "eliminadas": [
            {
                "titulo": it.titulo,
                "fecha": it.fecha,
                "por_name": it.creado_por.full_name if it.creado_por else None,
                "created_at": it.created_at,
                "eliminada_por": it.eliminado_por.full_name if it.eliminado_por else None,
                "eliminado_at": it.eliminado_at,
            }
            for it in svc.eliminadas(db, target)
        ],
        "tipos": svc.TIPOS,
    }


@router.post("", response_model=Entrada, status_code=status.HTTP_201_CREATED)
def agregar(body: AgendaIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    svc.ensure_use(user)
    para = user
    if body.para_id and body.para_id != user.id:
        para = db.get(User, body.para_id)
        if para is None or not para.is_active:
            raise NotFoundError("Esa persona no existe.")
    it = svc.agregar(db, user, body.model_dump(exclude={"para_id"}), para=para)
    db.commit()
    db.refresh(it)
    return _manual(user, it, fechas.now())


def _uno(db: DbSession, user: User, it: AgendaItem) -> dict[str, Any]:
    db.commit()
    db.refresh(it)
    return _manual(user, it, fechas.now())


@router.post("/{id_}/hecha", response_model=Entrada)
def hecha(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    it = svc.get_item(db, user, id_)
    svc.marcar_hecha(db, it, actor=user)
    return _uno(db, user, it)


@router.post("/{id_}/rechazar", response_model=Entrada)
def rechazar(id_: uuid.UUID, body: MotivoIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    it = svc.get_item(db, user, id_)
    svc.responder(db, it, "rechazada", body.motivo, actor=user)
    return _uno(db, user, it)


@router.post("/{id_}/justificar", response_model=Entrada)
def justificar(id_: uuid.UUID, body: MotivoIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    it = svc.get_item(db, user, id_)
    svc.responder(db, it, "justificada", body.motivo, actor=user)
    return _uno(db, user, it)


@router.delete("/{id_}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    svc.eliminar(db, svc.get_item(db, user, id_), actor=user)
    db.commit()
