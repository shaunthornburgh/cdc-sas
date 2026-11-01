import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, DbSession
from app.models import Movimiento, MovimientoEvento, MovimientosConfig, User
from app.models.enums import ALERTAS_GPS, EstadoMovimiento, TipoMovimiento
from app.schemas.movimientos import (
    AlertaIn,
    CampoIn,
    ConfigIn,
    ConfigRead,
    Evento,
    JustificarIn,
    MovimientoList,
    MovimientoRead,
    Opciones,
    Panel,
    RevisarIn,
    Ubicacion,
)
from app.services import fechas
from app.services import movimientos as svc

# K05 «Movimientos y GPS»: GPS alerts, their justification and review, and field work.
router = APIRouter(prefix="/movimientos", tags=["movimientos"])


def _emp(u: User) -> dict[str, Any]:
    return {"id": u.id, "full_name": u.full_name, "cargo": u.cargo, "perfil_txt": svc.perfil_txt(u)}


class _Ctx:
    """What every row needs: the viewer, the config and «now» (computed once per request)."""

    def __init__(self, db: DbSession, user: User):
        self.db, self.user = db, user
        self.cfg = svc.get_config(db)
        self.now = fechas.now()

    def read(self, m: Movimiento) -> dict[str, Any]:
        db, user, cfg, now = self.db, self.user, self.cfg, self.now
        alerta = m.tipo in ALERTAS_GPS
        dur = None if alerta else svc.minutos_campo(m, now)
        return {
            "id": m.id,
            "code": m.code,
            "empleado": _emp(m.empleado),
            "tipo": m.tipo,
            "tipo_txt": svc.TIPO_LABELS[m.tipo],
            "es_alerta": alerta,
            "estado": m.estado,
            "estado_txt": svc.ESTADO_LABELS[m.estado],
            "vencida": svc.vencida(m, cfg, now),
            "descuenta": svc.descuenta(m, cfg, now),
            "plazo_at": svc.plazo_at(m, cfg),
            "ocurrido_at": m.ocurrido_at,
            "fin_at": m.fin_at,
            "en_curso": svc.en_curso(m),
            "duracion_min": dur,
            "duracion_txt": None if dur is None else svc.fmt_dur(dur),
            "minutos_umbral": m.minutos_umbral,
            "lugar": m.lugar,
            "tiene_ubicacion": m.lat is not None and m.lng is not None,
            "detalle_txt": svc.detalle_txt(db, m, now),
            "motivo": m.motivo,
            "motivo_txt": svc.MOTIVO_LABELS[m.motivo] if m.motivo else None,
            "inmueble_codigo": m.inmueble_codigo,
            "inmueble_en_catalogo": m.inmueble_id is not None,
            "cliente": m.cliente,
            "motivo_texto": m.motivo_texto,
            "autorizo": m.autorizo,
            "autorizo_txt": svc.AUTORIZO_LABELS.get(m.autorizo or ""),
            "evidencias": m.evidencias,
            "observacion": m.observacion,
            "justificada_at": m.justificada_at,
            "revisa": ("Gerencia" if svc.revisor(m).value == "gerencia" else "Coordinación")
            if alerta
            else None,
            "revisado_por_name": m.revisado_por.full_name if m.revisado_por else None,
            "revisado_at": m.revisado_at,
            "nota_revision": m.nota_revision,
            "tipo_campo": m.tipo_campo,
            "tipo_campo_txt": svc.TIPO_CAMPO_LABELS[m.tipo_campo] if m.tipo_campo else None,
            "actividad_campo": m.actividad_campo,
            "actividad_campo_txt": svc.ACTIVIDAD_CAMPO_LABELS[m.actividad_campo]
            if m.actividad_campo
            else None,
            "cita_code": m.cita.code if m.cita else None,
            "acompanados": [u.full_name for u in svc.acompanados(db, m)],
            "detalle": m.detalle,
            "puede_justificar": svc.can_justify(user, m, cfg, now),
            "puede_revisar": svc.can_review(user, m),
            "puede_finalizar": svc.en_curso(m) and m.empleado_id == user.id,
        }


def _cfg(cfg: MovimientosConfig) -> dict[str, Any]:
    return {
        "minutos_alerta": cfg.minutos_alerta,
        "plazo_horas": cfg.plazo_horas,
        "minutos_opciones": list(svc.MINUTOS_OPCIONES),
        "updated_by_name": cfg.updated_by.full_name if cfg.updated_by else None,
        "updated_at": cfg.updated_at if cfg.updated_by_id else None,
    }


def _ev(e: MovimientoEvento) -> dict[str, Any]:
    return {
        "id": e.id,
        "tipo": e.tipo,
        "tipo_txt": svc.EVENTO_LABELS[e.tipo],
        "actor_name": e.actor.full_name if e.actor else None,
        "estado_antes": e.estado_antes,
        "estado_despues": e.estado_despues,
        "detalle": e.detalle,
        "created_at": e.created_at,
    }


def _filtros(
    desde: date | None,
    hasta: date | None,
    empleado_id: uuid.UUID | None,
    tipo: TipoMovimiento | None,
    estado: EstadoMovimiento | None,
) -> svc.Filtros:
    d1, d2 = svc.rango_defecto()
    return svc.Filtros(
        desde=desde or d1, hasta=hasta or d2, empleado_id=empleado_id, tipo=tipo, estado=estado
    )


@router.get("/opciones", response_model=Opciones)
def opciones(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    svc.ensure_use(user)
    p = svc.perfil(user)
    panel = svc.is_panel(user)
    d1, d2 = svc.rango_defecto()
    empleados: list[User] = []
    if panel:
        g = svc.gps_personas(db)
        otros = [
            u
            for u in db.query(User).filter(User.is_active.is_(True)).all()
            if svc.perfil(u) in ("coordinacion", "atencion")
        ]
        empleados = sorted([*g["con"], *otros], key=lambda u: u.full_name)
    campo = p in svc.CAMPO_DE
    return {
        "perfil": p,
        "panel": panel,
        "gerencia": user.cargo.value == "gerencia",
        "gps_activo": svc.gps_activo(db, user),
        "tipos": {k.value: v for k, v in svc.TIPO_LABELS.items()},
        "estados": {k.value: v for k, v in svc.ESTADO_LABELS.items()},
        "motivos": {k.value: v for k, v in svc.MOTIVO_LABELS.items()},
        "motivos_por_tipo": {
            k.value: [x.value for x in v] for k, v in svc.MOTIVOS_POR_TIPO.items()
        },
        "motivos_con_inmueble": [m.value for m in svc.MOTIVOS_CON_INMUEBLE],
        "autorizo": svc.AUTORIZO_LABELS,
        "tipos_campo": {t.value: svc.TIPO_CAMPO_LABELS[t] for t in svc.CAMPO_DE.get(p or "", ())},
        "actividades_campo": {k.value: v for k, v in svc.ACTIVIDAD_CAMPO_LABELS.items()},
        "alertas_propias": [t.value for t in svc.ALERTAS_DE.get(p or "", ())],
        "empleados": [_emp(u) for u in empleados],
        "asesores": [{"id": u.id, "txt": u.full_name} for u in svc.asesores(db)] if campo else [],
        "citas": [{"id": c.id, "txt": svc.cita_txt(c)} for c in svc.citas_para_apoyo(db)]
        if campo
        else [],
        "config": _cfg(svc.get_config(db)),
        "desde": d1,
        "hasta": d2,
        "jornada": "8:00 a. m.–6:00 p. m.",
    }


@router.get("", response_model=MovimientoList)
def listar(
    db: DbSession,
    user: CurrentUser,
    desde: date | None = None,
    hasta: date | None = None,
    empleado_id: uuid.UUID | None = None,
    tipo: TipoMovimiento | None = None,
    estado: EstadoMovimiento | None = None,
) -> dict[str, Any]:
    """Coordinación / Gerencia: everyone's. Anyone else: only their own."""
    f = _filtros(desde, hasta, empleado_id, tipo, estado)
    rows, por_tipo = svc.listar(db, user, f)
    c = _Ctx(db, user)
    per = svc.por_empleado(por_tipo, c.cfg, c.now)
    return {
        "items": [c.read(m) for m in rows],
        "desde": f.desde,
        "hasta": f.hasta,
        "kpis": svc.kpis(rows, c.cfg, c.now),
        "por_empleado": [r | {"empleado": _emp(r["empleado"])} for r in per],
        "pendientes": [c.read(m) for m in svc.pendientes_de(db, user)],
    }


@router.get("/export.csv")
def export_csv(
    db: DbSession,
    user: CurrentUser,
    desde: date | None = None,
    hasta: date | None = None,
    empleado_id: uuid.UUID | None = None,
    tipo: TipoMovimiento | None = None,
    estado: EstadoMovimiento | None = None,
) -> Response:
    f = _filtros(desde, hasta, empleado_id, tipo, estado)
    content, _ = svc.export_csv(db, user, f)
    db.commit()
    name = f"CDC_Movimientos_GPS_{f.desde.isoformat()}_a_{f.hasta.isoformat()}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/panel", response_model=Panel)
def panel(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    svc.ensure_panel(user)
    c = _Ctx(db, user)
    g = svc.gps_personas(db)
    hoy = svc.hoy()
    rows, _ = svc.listar(db, user, svc.Filtros(desde=hoy, hasta=hoy))
    alertas = [m for m in rows if m.tipo in ALERTAS_GPS]

    def campo(tipo: TipoMovimiento) -> dict[str, Any]:
        ab, ul = svc.en_campo(db, tipo)
        return {"abiertos": [c.read(m) for m in ab], "ultimo": c.read(ul) if ul else None}

    con = [m for m in rows if m.lat is not None and m.lng is not None]
    mapa = []
    if con:
        lats = [float(m.lat) for m in con]  # type: ignore[arg-type]
        lngs = [float(m.lng) for m in con]  # type: ignore[arg-type]
        span_lat = (max(lats) - min(lats)) or 1.0
        span_lng = (max(lngs) - min(lngs)) or 1.0
        for m, la, ln in zip(con, lats, lngs, strict=True):
            mapa.append(
                {
                    "id": m.id,
                    "code": m.code,
                    "empleado": m.empleado.full_name,
                    "tipo_txt": svc.TIPO_LABELS[m.tipo],
                    "estado": m.estado,
                    "hora": m.ocurrido_at,
                    "lugar": m.lugar,
                    "x": 0.5 if len(con) == 1 else round((ln - min(lngs)) / span_lng, 3),
                    "y": 0.5 if len(con) == 1 else round((max(lats) - la) / span_lat, 3),
                }
            )
    return {
        "config": _cfg(c.cfg),
        "cambios_config": [_ev(e) for e in svc.cambios_config(db)],
        "con_gps": [u.full_name for u in g["con"]],
        "sin_gps": [u.full_name for u in g["sin"]],
        "coordinador_campo": campo(TipoMovimiento.TRABAJO_CAMPO),
        "atencion_campo": campo(TipoMovimiento.ATENCION_CAMPO),
        "hoy": [c.read(m) for m in alertas],
        "mapa": mapa,
    }


@router.put("/config", response_model=ConfigRead)
def guardar_config(body: ConfigIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    sent = body.model_fields_set
    cfg = svc.guardar_config(
        db, user, body.minutos_alerta, body.plazo_horas, plazo="plazo_horas" in sent
    )
    db.commit()
    db.refresh(cfg)
    return _cfg(cfg)


@router.post("/alertas", response_model=MovimientoRead, status_code=status.HTTP_201_CREATED)
def reportar(body: AlertaIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    """The phone's GPS reports an alert for the signed-in person."""
    m = svc.reportar_alerta(db, user, body.model_dump())
    db.commit()
    db.refresh(m)
    return _Ctx(db, user).read(m)


@router.post("/campo", response_model=MovimientoRead, status_code=status.HTTP_201_CREATED)
def iniciar_campo(body: CampoIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    m = svc.iniciar_campo(db, user, body.model_dump())
    db.commit()
    db.refresh(m)
    return _Ctx(db, user).read(m)


@router.get("/{id_}", response_model=MovimientoRead)
def detalle(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return _Ctx(db, user).read(svc.get_movimiento(db, user, id_))


@router.get("/{id_}/historial", response_model=list[Evento])
def historial(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> list[dict[str, Any]]:
    return [_ev(e) for e in svc.historial(db, svc.get_movimiento(db, user, id_))]


def _act(db: DbSession, user: User, m: Movimiento) -> dict[str, Any]:
    db.commit()
    db.refresh(m)
    return _Ctx(db, user).read(m)


@router.post("/{id_}/justificar", response_model=MovimientoRead)
def justificar(
    id_: uuid.UUID, body: JustificarIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    m = svc.get_movimiento(db, user, id_)
    svc.justificar(db, m, body.model_dump(), actor=user)
    return _act(db, user, m)


@router.post("/{id_}/aprobar", response_model=MovimientoRead)
def aprobar(id_: uuid.UUID, body: RevisarIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    m = svc.get_movimiento(db, user, id_)
    svc.revisar(db, m, True, body.nota, actor=user)
    return _act(db, user, m)


@router.post("/{id_}/rechazar", response_model=MovimientoRead)
def rechazar(id_: uuid.UUID, body: RevisarIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    m = svc.get_movimiento(db, user, id_)
    svc.revisar(db, m, False, body.nota, actor=user)
    return _act(db, user, m)


@router.post("/{id_}/finalizar", response_model=MovimientoRead)
def finalizar(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    m = svc.get_movimiento(db, user, id_)
    svc.finalizar_campo(db, m, actor=user)
    return _act(db, user, m)


@router.post("/{id_}/ubicacion", response_model=Ubicacion)
def ubicacion(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    """Returns the coordinates and logs who looked (K05: «queda registrado quién la consultó»)."""
    m = svc.get_movimiento(db, user, id_)
    out = svc.ver_ubicacion(db, m, actor=user)
    db.commit()
    return out
