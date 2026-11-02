import uuid
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.rutas import CalificarIn, ImportarIn, LlegadaIn, ResponderIn, RutaIn
from app.services import fechas
from app.services import rutas as svc
from app.services.errors import NotFoundError
from app.services.pedidos import ZONAS

# G-083 «Programación de rutas» (asigna Coordinación; consultan Gerencia y Auxiliar) · M04.
router = APIRouter(prefix="/rutas", tags=["rutas"])


@router.get("/opciones", response_model=dict)
def opciones(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    svc.ensure_uso(user)
    hoy = fechas.local_date(fechas.now())
    lunes = hoy + timedelta(days=(7 - hoy.weekday()) % 7 or 7)  # next Monday
    return {
        "puede_programar": svc.puede_programar(user),
        "puede_consultar": svc.puede_consultar(user),
        "puede_calificar": user.cargo == "gerencia",
        "es_captador": svc.can_capture(user),
        "asesores": [{"id": u.id, "nombre": u.full_name} for u in svc.asesores(db)]
        if svc.puede_consultar(user)
        else [],
        "zonas": list(ZONAS),
        "motivos": svc.MOTIVOS,
        "dias": svc.DIAS,
        "estados": {k: v[0] for k, v in svc.ESTADOS.items()},
        "hoy": hoy,
        "proximo_lunes": lunes,
    }


@router.get("/mi-ruta", response_model=dict)
def mi_ruta(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return svc.mi_ruta(db, user)


@router.post("/llegada", response_model=dict, status_code=status.HTTP_201_CREATED)
def llegada(body: LlegadaIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    x = svc.llegar(db, user, body.zona_id, body.nota)
    db.commit()
    return {"zona_id": x.zona_id, "llegada_at": x.llegada_at}


@router.get("", response_model=dict)
def listar(
    db: DbSession,
    user: CurrentUser,
    desde: date | None = None,
    hasta: date | None = None,
    asesor_id: uuid.UUID | None = None,
    estado: str | None = None,
) -> dict[str, Any]:
    rs = svc.listar(db, user, desde=desde, hasta=hasta, asesor_id=asesor_id, estado=estado)
    return {"items": [svc.fila(r, user) for r in rs], "total": len(rs)}


@router.get("/ubicaciones", response_model=list[dict])
def ubicaciones(db: DbSession, user: CurrentUser) -> list[dict[str, Any]]:
    return svc.ubicaciones(db, user)


@router.get("/plantilla.csv")
def plantilla(user: CurrentUser) -> Response:
    svc.ensure_programar(user)
    return Response(
        svc.plantilla(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="CDC_Plantilla_Rutas.csv"'},
    )


@router.post("/importar", response_model=dict)
def importar(body: ImportarIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    out = svc.importar(db, body.texto, body.confirmar, actor=user)
    if body.confirmar:  # the review alone writes nothing
        db.commit()
    return out


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def crear(body: RutaIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    reemplaza = None
    if body.reemplaza_id:
        reemplaza = db.get(svc.Ruta, body.reemplaza_id)
        if reemplaza is None:
            raise NotFoundError("Esa ruta no existe.")
    data = body.model_dump(exclude={"reemplaza_id"})
    r = svc.crear(db, data, actor=user, reemplaza=reemplaza)
    db.commit()
    return svc.fila(r, user)


@router.get("/{id_}", response_model=dict)
def ver(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return svc.fila(svc.get(db, user, id_), user)


@router.post("/{id_}/cancelar", response_model=dict)
def cancelar(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    r = svc.get(db, user, id_)
    svc.cancelar(db, r, actor=user)
    db.commit()
    return svc.fila(r, user)


@router.post("/{id_}/responder", response_model=dict)
def responder(
    id_: uuid.UUID, body: ResponderIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    r = svc.get(db, user, id_)
    svc.responder(db, r, body.acepta, body.motivo, body.texto, actor=user)
    db.commit()
    return svc.fila(r, user)


@router.post("/{id_}/calificar", response_model=dict)
def calificar(
    id_: uuid.UUID, body: CalificarIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    r = svc.get(db, user, id_)
    svc.calificar(db, r, body.puntos, actor=user)
    db.commit()
    return svc.fila(r, user)
