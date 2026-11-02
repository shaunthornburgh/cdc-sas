import uuid
from typing import Any

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.models import AgendaItem, Aviso, Comunicado
from app.schemas.avisos import (
    AgendaIn,
    AgendaRead,
    AtenderIn,
    AvisoList,
    AvisoRead,
    ComunicadoIn,
    ComunicadoRead,
    Conteo,
    LeidosIn,
    Nota,
    NotaIn,
    Opciones,
)
from app.services import agenda
from app.services import avisos as svc

# G09 «Avisos y agenda» · M10 / C05 «Notificaciones».
router = APIRouter(prefix="/avisos", tags=["avisos"])


def _read(a: Aviso) -> dict[str, Any]:
    return {
        "id": a.id,
        "origen": a.origen,
        "tipo": a.tipo,
        "tipo_txt": a.tipo_txt,
        "nivel": a.nivel,
        "titulo": a.titulo,
        "detalle": a.detalle,
        "que_hacer": a.que_hacer,
        "limite_at": a.limite_at,
        "link": a.link,
        "accion_txt": a.accion_txt,
        "datos": a.datos or [],
        "requiere_accion": a.requiere_accion,
        "estado": a.estado,
        "atendido_at": a.atendido_at,
        "atendido_por_name": a.atendido_por.full_name if a.atendido_por else None,
        "resuelto_auto": a.resuelto_auto,
        "leido_at": a.leido_at,
        "enviado_por": (
            a.comunicado.creado_por.full_name if a.comunicado and a.comunicado.creado_por else None
        ),
        "created_at": a.created_at,
        "notas": [_nota(n) for n in a.notas],
    }


def _nota(n) -> dict[str, Any]:
    return {
        "id": n.id,
        "autor_name": n.autor.full_name if n.autor else None,
        "texto": n.texto,
        "created_at": n.created_at,
    }


def _item(it: AgendaItem) -> dict[str, Any]:
    return {
        "id": it.id,
        "fecha": it.fecha,
        "hora": it.hora,
        "hora_txt": agenda.hora_txt(it.hora),
        "titulo": it.titulo,
        "nota": it.nota,
        "prioridad": it.prioridad,
        "estado": it.estado,
        "hecha_at": it.hecha_at,
        "aviso_id": it.aviso_id,
        "aviso_titulo": it.aviso.titulo if it.aviso else None,
        "created_at": it.created_at,
    }


def _com(c: Comunicado, copias: list[Aviso]) -> dict[str, Any]:
    return {
        "id": c.id,
        "titulo": c.titulo,
        "cuerpo": c.cuerpo,
        "prioridad": c.prioridad,
        "audiencia": c.audiencia,
        "audiencia_txt": ", ".join(svc.AUDIENCIAS.get(k, k) for k in c.audiencia),
        "expira_el": c.expira_el,
        "creado_por": c.creado_por.full_name if c.creado_por else None,
        "created_at": c.created_at,
        "total": len(copias),
        "leidos": sum(1 for a in copias if a.leido_at),
        "lecturas": [{"nombre": a.destinatario.full_name, "leido_at": a.leido_at} for a in copias],
    }


@router.get("/opciones", response_model=Opciones)
def opciones(user: CurrentUser) -> dict[str, Any]:
    return {
        "puede_comunicar": svc.puede_comunicar(user),
        "audiencias": svc.audiencias_de(user),
        "gerencia": user.cargo.value == "gerencia",
    }


@router.get("/conteo", response_model=Conteo)
def conteo(db: DbSession, user: CurrentUser) -> dict[str, int]:
    """The bell: syncs this person's avisos and counts what waits for them."""
    svc.sincronizar(db, user)
    db.commit()
    return svc.conteo(db, user)


@router.get("", response_model=AvisoList)
def listar(db: DbSession, user: CurrentUser, vista: str = "por_atender") -> dict[str, Any]:
    """vista: por_atender · atendidos · resumen."""
    svc.sincronizar(db, user)
    db.commit()
    rows = svc.listar(db, user, vista)
    return {"items": [_read(a) for a in rows], "conteo": svc.conteo(db, user)}


@router.post("/leidos", response_model=Conteo)
def leidos(body: LeidosIn, db: DbSession, user: CurrentUser) -> dict[str, int]:
    svc.marcar_leidos(db, user, body.ids)
    db.commit()
    return svc.conteo(db, user)


# ---------------------------------------------------------------- comunicados


@router.get("/comunicados", response_model=list[ComunicadoRead])
def comunicados(db: DbSession, user: CurrentUser) -> list[dict[str, Any]]:
    return [_com(c, copias) for c, copias in svc.comunicados(db, user)]


@router.post("/comunicados", response_model=ComunicadoRead, status_code=status.HTTP_201_CREATED)
def enviar(body: ComunicadoIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    c, _ = svc.enviar_comunicado(db, body.model_dump(), actor=user)
    db.commit()
    copias = [a for _c, cs in svc.comunicados(db, user) if _c.id == c.id for a in cs]
    return _com(c, copias)


# ---------------------------------------------------------------- one aviso


def _uno(db: DbSession, a: Aviso) -> dict[str, Any]:
    db.commit()
    db.refresh(a)
    return _read(a)


@router.post("/{id_}/atender", response_model=AvisoRead)
def atender(id_: uuid.UUID, body: AtenderIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    a = svc.get_aviso(db, user, id_)
    svc.atender(db, a, actor=user, nota=body.nota)
    return _uno(db, a)


@router.post("/{id_}/reabrir", response_model=AvisoRead)
def reabrir(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    a = svc.get_aviso(db, user, id_)
    svc.reabrir(db, a, actor=user)
    return _uno(db, a)


@router.post("/{id_}/notas", response_model=Nota, status_code=status.HTTP_201_CREATED)
def nota(id_: uuid.UUID, body: NotaIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    n = svc.agregar_nota(db, svc.get_aviso(db, user, id_), body.texto, actor=user)
    db.commit()
    return _nota(n)


@router.post("/{id_}/agendar", response_model=AgendaRead, status_code=status.HTTP_201_CREATED)
def agendar(id_: uuid.UUID, body: AgendaIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    """G09 «Agendar en mi agenda»: also leaves a note on the aviso."""
    a = svc.get_aviso(db, user, id_)
    it = agenda.agregar(db, user, body.model_dump(), aviso=a)
    db.commit()
    return _item(it)
