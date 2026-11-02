import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, DbSession
from app.models import Sede, User
from app.schemas.asistencia import AsignarIn, ConfigIn, MarcarIn, RevisarIn, SedeIn
from app.services import asistencia as svc
from app.services import fechas
from app.services.errors import NotFoundError

# Z04 «Mi asistencia» · K17 «Asistencia y ausencias» · X08 sedes y horario (G-048 … G-051).
router = APIRouter(prefix="/asistencia", tags=["asistencia"])


def _res(db, r: svc.Resultado) -> dict[str, Any]:
    if not r.ok:
        return {
            "ok": False,
            "requiere_justificacion": r.requiere_justificacion,
            "titulo": r.titulo,
            "detalle": r.detalle,
            "opciones": r.opciones,
        }
    return {"ok": True, "marcacion": svc.fila(db, r.marcacion)}


@router.get("/mia", response_model=dict)
def mia(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return svc.mia(db, user)


@router.post("/entrada", response_model=dict)
def entrada(body: MarcarIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    r = svc.marcar_entrada(
        db, user, lat=body.lat, lng=body.lng, motivo=body.motivo, texto=body.texto
    )
    if r.ok:
        db.commit()
    return _res(db, r)


@router.post("/salida", response_model=dict)
def salida(body: MarcarIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    r = svc.marcar_salida(
        db, user, lat=body.lat, lng=body.lng, motivo=body.motivo, texto=body.texto
    )
    if r.ok:
        db.commit()
    return _res(db, r)


def _rango(desde: date | None, hasta: date | None) -> tuple[date, date]:
    hoy = fechas.local_date(fechas.now())
    return desde or hoy.replace(day=1), hasta or hoy


@router.get("/equipo", response_model=dict)
def equipo(
    db: DbSession, user: CurrentUser, desde: date | None = None, hasta: date | None = None
) -> dict[str, Any]:
    return svc.equipo(db, user, *_rango(desde, hasta))


@router.get("/export.csv")
def export(
    db: DbSession, user: CurrentUser, desde: date | None = None, hasta: date | None = None
) -> Response:
    d1, d2 = _rango(desde, hasta)
    return Response(
        svc.export_csv(db, user, d1, d2),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="CDC_Asistencia_{d1}_a_{d2}.csv"'},
    )


@router.post("/{id_}/revisar", response_model=dict)
def revisar(id_: uuid.UUID, body: RevisarIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    m = svc.get(db, user, id_)
    svc.revisar(db, m, body.que, body.acepta, actor=user)
    db.commit()
    return svc.fila(db, m)


# ---- settings, sedes and assigned locations


@router.get("/config", response_model=dict)
def config(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return svc.config_vista(db, user)


@router.put("/config", response_model=dict)
def guardar_config(body: ConfigIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    out = svc.guardar_config(db, body.valores, actor=user)
    db.commit()
    return out


@router.post("/sedes", response_model=dict, status_code=status.HTTP_201_CREATED)
def crear_sede(body: SedeIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    s = svc.crear_sede(db, body.model_dump(exclude_none=True), actor=user)
    db.commit()
    return {"id": s.id, "nombre": s.nombre}


@router.patch("/sedes/{id_}", response_model=dict)
def editar_sede(id_: uuid.UUID, body: SedeIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    s = db.get(Sede, id_)
    if s is None:
        raise NotFoundError("Esa sede no existe.")
    svc.editar_sede(db, s, body.model_dump(exclude_none=True), actor=user)
    db.commit()
    return {"id": s.id, "activa": s.activa, "principal": s.principal}


@router.put("/ubicacion/{user_id}", response_model=dict)
def asignar(
    user_id: uuid.UUID, body: AsignarIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    u = db.get(User, user_id)
    if u is None or not u.is_active:
        raise NotFoundError("Esa persona no existe.")
    ua = svc.asignar(db, u, body.sede_id, actor=user)
    db.commit()
    return {"user_id": u.id, "sede": ua.sede.nombre}
