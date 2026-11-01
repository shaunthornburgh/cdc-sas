"""Movimientos y GPS (prototypes K05 / K05-ger, M05 «Justificar», K16 / C09 «Trabajo en campo»).

* **Alerts** (G-002, G-036, G-039): «salida de ruta» and «tiempo detenido» for asesores with
  Captación; «salida de la zona» and «tiempo detenido» for the Coordinador and «tiempo detenido»
  for Atención y Preventa, only while they are in the field (their GPS is on only then). Alerts
  are reported by the person's phone, only during the working day (8:00 a. m.–6:00 p. m.).
* **Justification** (M05): the person picks what happened. A cita or an inventario needs the
  inmueble code, the client and an observation; a personal reason needs the reason, and for a
  salida who authorized it (a tiempo detenido can carry evidence).
* **Review**: Coordinación reviews asesores and Atención y Preventa; Gerencia reviews the
  Coordinador (K05-ger, G-048). A rejected justification, or an alert left unjustified past the
  deadline, takes 1 point off the month's rendimiento. The deadline is «PENDIENTE DE
  CONFIGURACIÓN» until someone sets it; until then nothing expires.
* **Field records** (K16 / C09): the Coordinador (apoyo en cita, acompañamiento en ruta, salida
  grupal, otra) and Atención y Preventa (apoyo en cita, otra) start and finish «trabajo en campo».
  They are records, not alerts: no justification and no review.
* **Privacy**: the location of an alert is only returned through ``ver_ubicacion``, which logs who
  looked and when («Nada de seguimiento oculto»).
* **History**: every action is a ``MovimientoEvento`` with actor, time, and state before/after.
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cita, Inmueble, Movimiento, MovimientoEvento, MovimientosConfig, User
from app.models.enums import (
    ALERTAS_GPS,
    ActividadCampo,
    Cargo,
    EstadoCita,
    EstadoMovimiento,
    MotivoMovimiento,
    TipoCampo,
    TipoEventoMovimiento,
    TipoMovimiento,
)
from app.services import fechas
from app.services.citas import TIPO_LABELS as CITA_TIPO_LABELS
from app.services.errors import ConflictError, DomainError, NotFoundError, PermissionDeniedError
from app.services.policies import LEAD_FUNCIONES, can_capture, has_commercial_activity

T = TipoMovimiento
E = EstadoMovimiento
M = MotivoMovimiento

TIPO_LABELS = {
    T.SALIDA_RUTA: "Salida de ruta",
    T.TIEMPO_DETENIDO: "Tiempo detenido",
    T.SALIDA_ZONA: "Salida de la zona (Coordinador)",
    T.TRABAJO_CAMPO: "Trabajo en campo (Coordinador)",
    T.ATENCION_CAMPO: "Atención en campo",
}
ESTADO_LABELS = {
    E.SIN_JUSTIFICAR: "Sin justificar",
    E.POR_REVISAR: "Justificada · por revisar",
    E.APROBADA: "✓ Aprobada",
    E.RECHAZADA: "✕ Rechazada · −1 punto",
    E.REGISTRO: "Registro de campo",
}
MOTIVO_LABELS = {
    M.CITA_FUERA_RUTA: "Cita fuera de ruta",
    M.PERMISO_PERSONAL: "Permiso personal",
    M.CITA_NO_PROGRAMADA: "Cita no programada",
    M.INVENTARIO: "Inventario",
    M.IMPREVISTO_PERSONAL: "Imprevisto personal",
}
_SALIDA = (M.CITA_FUERA_RUTA, M.PERMISO_PERSONAL)
MOTIVOS_POR_TIPO = {
    T.SALIDA_RUTA: _SALIDA,
    T.SALIDA_ZONA: _SALIDA,
    T.TIEMPO_DETENIDO: (M.CITA_NO_PROGRAMADA, M.INVENTARIO, M.IMPREVISTO_PERSONAL),
}
MOTIVOS_CON_INMUEBLE = frozenset({M.CITA_FUERA_RUTA, M.CITA_NO_PROGRAMADA, M.INVENTARIO})
AUTORIZO_LABELS = {
    "coordinacion": "Coordinación",
    "gerencia": "Gerencia",
    "pendiente": "Nadie aún: pidió autorización",
}
TIPO_CAMPO_LABELS = {
    TipoCampo.APOYO_CITA: "Apoyo en cita",
    TipoCampo.ACOMPANAMIENTO_RUTA: "Acompañamiento en ruta",
    TipoCampo.SALIDA_GRUPAL: "Salida grupal",
    TipoCampo.OTRA: "Otra actividad de campo",
}
ACTIVIDAD_CAMPO_LABELS = {
    ActividadCampo.CAPTACION: "Captación",
    ActividadCampo.VISITA_PROPIETARIO: "Visita a propietario",
    ActividadCampo.CITA_VENTA: "Cita de venta",
    ActividadCampo.CITA_ARRIENDO: "Cita de arriendo",
    ActividadCampo.INVENTARIO: "Inventario",
    ActividadCampo.OTRA: "Otra",
}
EVENTO_LABELS = {
    TipoEventoMovimiento.CREADO: "Registrado",
    TipoEventoMovimiento.JUSTIFICADO: "Justificado",
    TipoEventoMovimiento.APROBADO: "Aprobado",
    TipoEventoMovimiento.RECHAZADO: "Rechazado",
    TipoEventoMovimiento.FINALIZADO: "Finalizado",
    TipoEventoMovimiento.UBICACION: "Consultó la ubicación",
    TipoEventoMovimiento.CONFIG: "Cambió la configuración",
    TipoEventoMovimiento.DESCARGA: "Descargó el registro",
}

# Alerts each GPS profile can get.
ALERTAS_DE = {
    "asesor": (T.SALIDA_RUTA, T.TIEMPO_DETENIDO),
    "coordinacion": (T.SALIDA_ZONA, T.TIEMPO_DETENIDO),
    "atencion": (T.TIEMPO_DETENIDO,),
}
CAMPO_DE = {
    "coordinacion": tuple(TipoCampo),
    "atencion": (TipoCampo.APOYO_CITA, TipoCampo.OTRA),  # no acompañamiento en ruta (G-040)
}
PANEL = (Cargo.GERENCIA, Cargo.COORDINACION)
JORNADA = (time(8, 0), time(18, 0))
DESCUENTO = 1  # point off per rejected / expired alert (G-036)
MINUTOS_OPCIONES = (15, 20, 30)
DIAS_POR_DEFECTO = 30
MAX_ATRASO = timedelta(hours=24)  # a phone that was offline can report up to a day late


# ---------------------------------------------------------------- who


def perfil(user: User) -> str | None:
    """GPS profile: asesor (Captación) · coordinacion · atencion (Atención y Preventa)."""
    if not user.is_active:
        return None
    if user.cargo == Cargo.COORDINACION:
        return "coordinacion"
    if user.funcion in LEAD_FUNCIONES:
        return "atencion"
    if can_capture(user):
        return "asesor"
    return None


def perfil_txt(user: User) -> str:
    p = perfil(user)
    if p == "asesor":
        return "Asesor · Captación"
    if p == "coordinacion":
        return "Coordinador · trabajo en campo"
    if p == "atencion":
        return "Atención y Preventa · apoyo en campo"
    return ""


def is_panel(user: User) -> bool:
    return user.is_active and user.cargo in PANEL


def can_use(user: User) -> bool:
    return is_panel(user) or perfil(user) is not None


def ensure_use(user: User) -> None:
    if not can_use(user):
        raise PermissionDeniedError(
            "Movimientos y GPS es de quien tiene GPS (Captación, Coordinación en campo, "
            "Atención y Preventa en campo) y de Coordinación y Gerencia."
        )


def ensure_panel(user: User) -> None:
    if not is_panel(user):
        raise PermissionDeniedError("Esto lo ven Coordinación y Gerencia.")


def revisor(m: Movimiento) -> Cargo:
    """The Coordinador's alerts are reviewed by Gerencia; everyone else's by Coordinación."""
    return Cargo.GERENCIA if m.empleado.cargo == Cargo.COORDINACION else Cargo.COORDINACION


def can_see(user: User, m: Movimiento) -> bool:
    return is_panel(user) or m.empleado_id == user.id


def can_review(user: User, m: Movimiento) -> bool:
    return (
        user.is_active
        and m.estado == E.POR_REVISAR
        and user.cargo == revisor(m)
        and m.empleado_id != user.id
    )


def can_justify(user: User, m: Movimiento, cfg: MovimientosConfig, now: datetime) -> bool:
    return m.empleado_id == user.id and m.estado == E.SIN_JUSTIFICAR and not vencida(m, cfg, now)


def get_movimiento(db: Session, user: User, id_: uuid.UUID) -> Movimiento:
    ensure_use(user)
    m = db.get(Movimiento, id_)
    if m is None or not can_see(user, m):
        raise NotFoundError("Ese movimiento no existe.")
    return m


# ---------------------------------------------------------------- config


def get_config(db: Session) -> MovimientosConfig:
    cfg = db.get(MovimientosConfig, 1)
    if cfg is None:
        cfg = MovimientosConfig(id=1, minutos_alerta=20, plazo_horas=None)
        db.add(cfg)
        db.flush()
    return cfg


def guardar_config(
    db: Session, actor: User, minutos_alerta: int | None, plazo_horas: int | None, *, plazo=False
) -> MovimientosConfig:
    """Coordinación and Gerencia change the alert time («Configuración y mapa») and the deadline.

    `plazo=True` means `plazo_horas` was sent (None then clears it back to «pendiente»).
    """
    ensure_panel(actor)
    cfg = get_config(db)
    antes = cfg.as_dict()
    partes = []
    if minutos_alerta is not None and minutos_alerta != cfg.minutos_alerta:
        if not 5 <= minutos_alerta <= 240:
            raise DomainError("El tiempo de alerta va de 5 a 240 minutos.")
        partes.append(f"Tiempo de alerta: {cfg.minutos_alerta} → {minutos_alerta} min")
        cfg.minutos_alerta = minutos_alerta
    if plazo and plazo_horas != cfg.plazo_horas:
        if plazo_horas is not None and not 1 <= plazo_horas <= 168:
            raise DomainError("El plazo para justificar va de 1 a 168 horas.")
        partes.append(
            f"Plazo para justificar: {_plazo_txt(cfg.plazo_horas)} → {_plazo_txt(plazo_horas)}"
        )
        cfg.plazo_horas = plazo_horas
    if partes:
        cfg.updated_by_id = actor.id
        cfg.updated_by = actor
        _evento(
            db,
            None,
            TipoEventoMovimiento.CONFIG,
            actor,
            detalle=" · ".join(partes),
            antes=str(antes["minutos_alerta"]),
            despues=str(cfg.minutos_alerta),
        )
    db.flush()
    return cfg


def _plazo_txt(h: int | None) -> str:
    return "pendiente" if h is None else f"{h} h"


def vencida(m: Movimiento, cfg: MovimientosConfig, now: datetime) -> bool:
    """An alert still unjustified after the deadline (only once a deadline is configured)."""
    return (
        m.estado == E.SIN_JUSTIFICAR
        and cfg.plazo_horas is not None
        and now > m.ocurrido_at + timedelta(hours=cfg.plazo_horas)
    )


def plazo_at(m: Movimiento, cfg: MovimientosConfig) -> datetime | None:
    if m.tipo not in ALERTAS_GPS or cfg.plazo_horas is None:
        return None
    return m.ocurrido_at + timedelta(hours=cfg.plazo_horas)


def descuenta(m: Movimiento, cfg: MovimientosConfig, now: datetime) -> bool:
    return m.estado == E.RECHAZADA or vencida(m, cfg, now)


# ---------------------------------------------------------------- helpers


def _evento(
    db: Session,
    m: Movimiento | None,
    tipo: TipoEventoMovimiento,
    actor: User | None,
    *,
    detalle: str | None = None,
    antes: str | None = None,
    despues: str | None = None,
) -> MovimientoEvento:
    ev = MovimientoEvento(
        movimiento_id=m.id if m else None,
        tipo=tipo,
        actor_id=actor.id if actor else None,
        estado_antes=antes,
        estado_despues=despues,
        detalle=(detalle or None) and detalle[:500],
    )
    ev.actor = actor
    db.add(ev)
    return ev


def en_jornada(dt: datetime) -> bool:
    t = dt.astimezone(fechas.BOGOTA).time()
    return JORNADA[0] <= t < JORNADA[1]


def hoy() -> date:
    return fechas.local_date(fechas.now())


def rango_defecto() -> tuple[date, date]:
    """K05-ger: the last 30 days, today included."""
    d = hoy()
    return d - timedelta(days=DIAS_POR_DEFECTO - 1), d


def fin_efectivo(m: Movimiento, now: datetime) -> datetime | None:
    """Field work still open counts until now, but never past the end of that working day."""
    if m.tipo in ALERTAS_GPS:
        return None
    if m.fin_at is not None:
        return m.fin_at
    cierre = datetime.combine(fechas.local_date(m.ocurrido_at), JORNADA[1], tzinfo=fechas.BOGOTA)
    return max(m.ocurrido_at, min(now, cierre))


def minutos_campo(m: Movimiento, now: datetime) -> int:
    fin = fin_efectivo(m, now)
    return int((fin - m.ocurrido_at).total_seconds() // 60) if fin else 0


def fmt_dur(minutos: int) -> str:
    """«2 h 10 min» · «45 min»."""
    h, mi = divmod(minutos, 60)
    return f"{h} h {mi:02d} min" if h else f"{mi} min"


def fmt_horas(minutos: int) -> str:
    """K05-ger KPI: «8:35 h»."""
    h, mi = divmod(minutos, 60)
    return f"{h}:{mi:02d} h"


def en_curso(m: Movimiento) -> bool:
    return m.tipo not in ALERTAS_GPS and m.fin_at is None


def acompanados(db: Session, m: Movimiento) -> list[User]:
    ids = [uuid.UUID(x) for x in (m.acompanados_ids or [])]
    if not ids:
        return []
    by_id = {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids))).unique()}
    return [by_id[i] for i in ids if i in by_id]


def _nombres(us: list[User]) -> str:
    n = [u.full_name.split()[0] for u in us]
    return n[0] if len(n) == 1 else ", ".join(n[:-1]) + " y " + n[-1] if n else ""


def detalle_txt(db: Session, m: Movimiento, now: datetime) -> str:
    """The «Detalle» column of K05: what happened, or how it was justified."""
    if m.tipo in ALERTAS_GPS:
        if m.motivo is None:
            base = {
                T.SALIDA_RUTA: "Salida de la ruta asignada",
                T.TIEMPO_DETENIDO: f"Más de {m.minutos_umbral or 20} min en el mismo lugar",
                T.SALIDA_ZONA: "Salida de la zona de la actividad",
            }[m.tipo]
            partes = [base, m.lugar, "pendiente de justificar"]
        elif m.motivo in MOTIVOS_CON_INMUEBLE:
            partes = [MOTIVO_LABELS[m.motivo], m.inmueble_codigo, m.cliente]
        else:
            aut = f"autorizó {AUTORIZO_LABELS[m.autorizo].lower()}" if m.autorizo else None
            if m.autorizo == "pendiente":
                aut = "pidió autorización"
            partes = [MOTIVO_LABELS[m.motivo], m.motivo_texto, aut]
        return " · ".join(p for p in partes if p)
    con: str | None = None
    if m.tipo_campo == TipoCampo.APOYO_CITA and m.cita is not None:
        con = f"{m.cita.code}" + (f" · {m.cita.asesor_name}" if m.cita.asesor_name else "")
    elif m.tipo_campo in (TipoCampo.ACOMPANAMIENTO_RUTA, TipoCampo.SALIDA_GRUPAL):
        con = _nombres(acompanados(db, m)) or None
    act = ACTIVIDAD_CAMPO_LABELS[m.actividad_campo].lower() if m.actividad_campo else None
    dur = "en curso" if en_curso(m) else fmt_dur(minutos_campo(m, now))
    tc = TIPO_CAMPO_LABELS[m.tipo_campo] if m.tipo_campo else TIPO_LABELS[m.tipo]
    return " · ".join(p for p in (tc, con, act, m.detalle, dur) if p)


# ---------------------------------------------------------------- GPS reports (alerts)


def campo_abierto(db: Session, user: User) -> Movimiento | None:
    return db.scalar(
        select(Movimiento).where(
            Movimiento.empleado_id == user.id,
            Movimiento.tipo.in_((T.TRABAJO_CAMPO, T.ATENCION_CAMPO)),
            Movimiento.fin_at.is_(None),
        )
    )


def gps_activo(db: Session, user: User, now: datetime | None = None) -> bool:
    """Captación: during the working day. Coordinador / Atención: only while in the field."""
    now = now or fechas.now()
    p = perfil(user)
    if p is None or not en_jornada(now):
        return False
    return p == "asesor" or campo_abierto(db, user) is not None


def reportar_alerta(
    db: Session, actor: User, data: dict[str, Any], *, now: datetime | None = None
) -> Movimiento:
    """The person's phone reports an alert (in the real software, the GPS does it on its own)."""
    now = now or fechas.now()
    p = perfil(actor)
    if p is None:
        raise PermissionDeniedError("No tienes GPS: solo se activa con Captación o en campo.")
    tipo = data["tipo"]
    if tipo not in ALERTAS_DE[p]:
        raise DomainError(f"«{TIPO_LABELS[tipo]}» no aplica a tu cargo.")
    cuando = data.get("ocurrido_at") or now
    if cuando > now + timedelta(minutes=5) or cuando < now - MAX_ATRASO:
        raise DomainError("La hora de la alerta no es válida.")
    if not en_jornada(cuando):
        raise DomainError("El GPS solo registra en la jornada, de 8:00 a. m. a 6:00 p. m.")
    if p != "asesor" and campo_abierto(db, actor) is None:
        raise DomainError("Tu GPS solo está activo mientras estás en campo.")
    cfg = get_config(db)
    m = Movimiento(
        empleado_id=actor.id,
        tipo=tipo,
        estado=E.SIN_JUSTIFICAR,
        ocurrido_at=cuando,
        minutos_umbral=cfg.minutos_alerta if tipo == T.TIEMPO_DETENIDO else None,
        lat=data.get("lat"),
        lng=data.get("lng"),
        lugar=(data.get("lugar") or "").strip() or None,
        creado_por_id=actor.id,
    )
    m.empleado = actor
    db.add(m)
    db.flush()
    _evento(db, m, TipoEventoMovimiento.CREADO, actor, detalle="GPS del celular", despues=m.estado)
    db.flush()
    return m


# ---------------------------------------------------------------- justify and review


def _txt(v: Any) -> str:
    return (v or "").strip() if isinstance(v, str) or v is None else str(v)


def justificar(
    db: Session, m: Movimiento, data: dict[str, Any], *, actor: User, now: datetime | None = None
) -> Movimiento:
    now = now or fechas.now()
    if m.empleado_id != actor.id:
        raise PermissionDeniedError("Solo la persona de la alerta la justifica.")
    if m.tipo not in ALERTAS_GPS:
        raise DomainError("Los registros de campo no se justifican.")
    if m.estado != E.SIN_JUSTIFICAR:
        raise ConflictError("Esta alerta ya fue justificada.")
    cfg = get_config(db)
    if vencida(m, cfg, now):
        raise ConflictError("Venció el plazo para justificar: la alerta descuenta 1 punto.")
    motivo = data.get("motivo")
    if motivo not in MOTIVOS_POR_TIPO[m.tipo]:
        raise DomainError("Elige qué pasó.")
    obs = _txt(data.get("observacion"))
    if motivo in MOTIVOS_CON_INMUEBLE:
        codigo, cliente = _txt(data.get("inmueble_codigo")).upper(), _txt(data.get("cliente"))
        if not codigo or not cliente or not obs:
            raise DomainError("Escribe el código del inmueble, el cliente y la observación.")
        m.inmueble_codigo, m.cliente = codigo[:40], cliente[:200]
        m.inmueble = db.scalar(select(Inmueble).where(Inmueble.codigo == codigo))
        m.motivo_texto = m.autorizo = None
    else:
        texto = _txt(data.get("motivo_texto"))
        if len(texto) < 3:
            raise DomainError("Escribe el motivo.")
        m.motivo_texto = texto[:300]
        if m.tipo in (T.SALIDA_RUTA, T.SALIDA_ZONA):
            aut = data.get("autorizo")
            if aut not in AUTORIZO_LABELS:
                raise DomainError("Elige quién autorizó la salida.")
            m.autorizo = aut
        else:
            m.evidencias = int(data.get("evidencias") or 0)
            if not 0 <= m.evidencias <= 10:
                raise DomainError("Revisa el número de archivos adjuntos.")
        m.inmueble_codigo = m.cliente = None
        m.inmueble = None
    m.motivo = motivo
    m.observacion = obs[:500] or None
    m.justificada_at = now
    m.estado = E.POR_REVISAR
    _evento(
        db,
        m,
        TipoEventoMovimiento.JUSTIFICADO,
        actor,
        detalle=detalle_txt(db, m, now),
        antes=E.SIN_JUSTIFICAR,
        despues=E.POR_REVISAR,
    )
    db.flush()
    return m


def revisar(
    db: Session, m: Movimiento, aprobar: bool, nota: str | None, *, actor: User
) -> Movimiento:
    if m.estado != E.POR_REVISAR:
        raise ConflictError(
            "Esta alerta todavía no está justificada."
            if m.estado == E.SIN_JUSTIFICAR
            else "Esta justificación ya fue revisada."
            if m.estado in (E.APROBADA, E.RECHAZADA)
            else "Los registros de campo no se revisan."
        )
    if not can_review(actor, m):
        quien = "Gerencia" if revisor(m) == Cargo.GERENCIA else "Coordinación"
        sujeto = "del Coordinador" if revisor(m) == Cargo.GERENCIA else "de esta persona"
        raise PermissionDeniedError(f"Las justificaciones {sujeto} las revisa {quien}.")
    m.estado = E.APROBADA if aprobar else E.RECHAZADA
    m.revisado_por_id = actor.id
    m.revisado_por = actor
    m.revisado_at = fechas.now()
    m.nota_revision = _txt(nota)[:300] or None
    _evento(
        db,
        m,
        TipoEventoMovimiento.APROBADO if aprobar else TipoEventoMovimiento.RECHAZADO,
        actor,
        detalle=m.nota_revision or (None if aprobar else "Descuenta 1 punto en el rendimiento"),
        antes=E.POR_REVISAR,
        despues=m.estado,
    )
    db.flush()
    return m


# ---------------------------------------------------------------- field work (K16 / C09)


def citas_para_apoyo(db: Session) -> list[Cita]:
    """Citas from today to 7 days ahead that are still going to happen."""
    d1 = fechas.start_of_day(hoy())
    return list(
        db.scalars(
            select(Cita)
            .where(
                Cita.scheduled_at >= d1,
                Cita.scheduled_at < d1 + timedelta(days=8),
                Cita.estado.in_((EstadoCita.PENDIENTE, EstadoCita.ACEPTADA)),
            )
            .order_by(Cita.scheduled_at)
        ).unique()
    )


def cita_txt(c: Cita) -> str:
    """«CIT-0412 · Visita a inmueble · venta · hoy 16:00 · Juan Ejemplo»."""
    partes = [c.code, CITA_TIPO_LABELS[c.tipo], fechas.fmt(c.scheduled_at), c.asesor_name]
    return " · ".join(p for p in partes if p)


def asesores(db: Session) -> list[User]:
    """Who the Coordinador can go out with: every active asesor."""
    us = db.scalars(
        select(User).where(User.is_active.is_(True), User.cargo == Cargo.ASESOR)
    ).unique()
    return sorted((u for u in us if has_commercial_activity(u)), key=lambda u: u.full_name)


def iniciar_campo(
    db: Session, actor: User, data: dict[str, Any], *, now: datetime | None = None
) -> Movimiento:
    now = now or fechas.now()
    p = perfil(actor)
    if p not in CAMPO_DE:
        raise PermissionDeniedError(
            "El trabajo en campo lo registran el Coordinador y Atención y Preventa."
        )
    if (abierto := campo_abierto(db, actor)) is not None:
        hora = fechas.fmt(abierto.ocurrido_at)
        raise ConflictError(f"Ya estás en campo desde {hora}: finalízalo primero.")
    if not en_jornada(now):
        raise DomainError(
            "El trabajo en campo se registra en la jornada, de 8:00 a. m. a 6:00 p. m."
        )
    tc = data.get("tipo_campo")
    if tc not in CAMPO_DE[p]:
        raise DomainError("Elige el tipo de trabajo en campo.")
    act = data.get("actividad_campo")
    if act is None:
        raise DomainError("Elige la actividad.")
    m = Movimiento(
        empleado_id=actor.id,
        tipo=T.TRABAJO_CAMPO if p == "coordinacion" else T.ATENCION_CAMPO,
        estado=E.REGISTRO,
        ocurrido_at=now,
        tipo_campo=tc,
        actividad_campo=act,
        detalle=_txt(data.get("detalle"))[:300] or None,
        lugar=_txt(data.get("lugar"))[:120] or None,
        lat=data.get("lat"),
        lng=data.get("lng"),
        creado_por_id=actor.id,
        acompanados_ids=[],
    )
    if tc == TipoCampo.APOYO_CITA:
        cita = db.get(Cita, data.get("cita_id")) if data.get("cita_id") else None
        if cita is None or cita.estado not in (
            EstadoCita.PENDIENTE,
            EstadoCita.ACEPTADA,
            EstadoCita.REALIZADA,
        ):
            raise DomainError("Elige la cita que apoyas.")
        m.cita = cita
    elif tc in (TipoCampo.ACOMPANAMIENTO_RUTA, TipoCampo.SALIDA_GRUPAL):
        validos = {u.id for u in asesores(db)}
        ids = list(dict.fromkeys(data.get("acompanados_ids") or []))
        if any(i not in validos for i in ids):
            raise DomainError("Elige asesores activos.")
        if tc == TipoCampo.ACOMPANAMIENTO_RUTA and len(ids) != 1:
            raise DomainError("Elige el asesor que acompañas.")
        if tc == TipoCampo.SALIDA_GRUPAL and len(ids) < 2:
            raise DomainError("Una salida grupal es con dos asesores o más.")
        m.acompanados_ids = [str(i) for i in ids]
    m.empleado = actor
    db.add(m)
    db.flush()
    _evento(
        db,
        m,
        TipoEventoMovimiento.CREADO,
        actor,
        detalle="Inició trabajo en campo · GPS activo",
        despues=E.REGISTRO,
    )
    db.flush()
    return m


def finalizar_campo(
    db: Session, m: Movimiento, *, actor: User, now: datetime | None = None
) -> Movimiento:
    now = now or fechas.now()
    if m.empleado_id != actor.id:
        raise PermissionDeniedError("Solo quien está en campo lo finaliza.")
    if m.tipo in ALERTAS_GPS:
        raise DomainError("Las alertas no se finalizan.")
    if m.fin_at is not None:
        raise ConflictError("Este trabajo en campo ya terminó.")
    m.fin_at = max(m.ocurrido_at, now)
    _evento(
        db,
        m,
        TipoEventoMovimiento.FINALIZADO,
        actor,
        detalle=f"Duración {fmt_dur(m.duracion_min or 0)} · GPS apagado",
        antes=E.REGISTRO,
        despues=E.REGISTRO,
    )
    db.flush()
    return m


# ---------------------------------------------------------------- location (privacy log)


def ver_ubicacion(db: Session, m: Movimiento, *, actor: User) -> dict[str, Any]:
    if not (is_panel(actor) or m.empleado_id == actor.id):
        raise PermissionDeniedError("La ubicación la ven Coordinación y Gerencia.")
    if m.lat is None or m.lng is None:
        raise NotFoundError("Este movimiento no tiene ubicación registrada.")
    if m.empleado_id != actor.id:
        _evento(db, m, TipoEventoMovimiento.UBICACION, actor, detalle=m.lugar)
        db.flush()
    return {"lat": float(m.lat), "lng": float(m.lng), "lugar": m.lugar}


# ---------------------------------------------------------------- list, KPIs, per person


@dataclass
class Filtros:
    desde: date
    hasta: date
    empleado_id: uuid.UUID | None = None
    tipo: TipoMovimiento | None = None
    estado: EstadoMovimiento | None = None


def _en_rango(db: Session, viewer: User, f: Filtros) -> list[Movimiento]:
    if f.desde > f.hasta:
        raise DomainError("La fecha «Desde» no puede ser posterior a «Hasta».")
    q = select(Movimiento).where(
        Movimiento.ocurrido_at >= fechas.start_of_day(f.desde),
        Movimiento.ocurrido_at < fechas.start_of_day(f.hasta + timedelta(days=1)),
    )
    if not is_panel(viewer):
        q = q.where(Movimiento.empleado_id == viewer.id)
    return list(db.scalars(q.order_by(Movimiento.ocurrido_at.desc())).unique())


def listar(db: Session, viewer: User, f: Filtros) -> tuple[list[Movimiento], list[Movimiento]]:
    """Returns (filtered list, everything in range with only the tipo filter: per person)."""
    ensure_use(viewer)
    rango = _en_rango(db, viewer, f)
    por_tipo = [m for m in rango if f.tipo is None or m.tipo == f.tipo]
    rows = [
        m
        for m in por_tipo
        if (f.empleado_id is None or m.empleado_id == f.empleado_id)
        and (f.estado is None or m.estado == f.estado)
    ]
    return rows, por_tipo


def pendientes_de(db: Session, user: User) -> list[Movimiento]:
    """The person's alerts still to justify (any date), oldest first."""
    return list(
        db.scalars(
            select(Movimiento)
            .where(Movimiento.empleado_id == user.id, Movimiento.estado == E.SIN_JUSTIFICAR)
            .order_by(Movimiento.ocurrido_at)
        ).unique()
    )


def kpis(rows: list[Movimiento], cfg: MovimientosConfig, now: datetime) -> dict[str, Any]:
    """K05-ger's six cards, over the filtered list."""
    al = [m for m in rows if m.tipo in ALERTAS_GPS]
    just = [m for m in al if m.estado != E.SIN_JUSTIFICAR]
    campo = [m for m in rows if m.tipo == T.TRABAJO_CAMPO]
    return {
        "alertas": len(al),
        "justificadas": len(just),
        "justificadas_pct": round(100 * len(just) / len(al)) if al else None,
        "sin_justificar": sum(1 for m in al if m.estado == E.SIN_JUSTIFICAR),
        "vencidas": sum(1 for m in al if vencida(m, cfg, now)),
        "por_revisar": sum(1 for m in al if m.estado == E.POR_REVISAR),
        "por_revisar_gerencia": sum(
            1 for m in al if m.estado == E.POR_REVISAR and revisor(m) == Cargo.GERENCIA
        ),
        "rechazadas": sum(1 for m in al if m.estado == E.RECHAZADA),
        "coord_campo_min": sum(minutos_campo(m, now) for m in campo),
        "coord_campo_salidas": len(campo),
    }


def por_empleado(
    rows: list[Movimiento], cfg: MovimientosConfig, now: datetime
) -> list[dict[str, Any]]:
    """K05-ger «Por empleado»: alerts, justified, pending, rejected and hours in the field."""
    out: dict[uuid.UUID, dict[str, Any]] = {}
    for m in rows:
        r = out.setdefault(
            m.empleado_id,
            {
                "empleado": m.empleado,
                "alertas": 0,
                "justificadas": 0,
                "sin_justificar": 0,
                "rechazadas": 0,
                "vencidas": 0,
                "campo_min": 0,
            },
        )
        if m.tipo in ALERTAS_GPS:
            r["alertas"] += 1
            if m.estado == E.SIN_JUSTIFICAR:
                r["sin_justificar"] += 1
                r["vencidas"] += vencida(m, cfg, now)
            else:
                r["justificadas"] += 1
            r["rechazadas"] += m.estado == E.RECHAZADA
        else:
            r["campo_min"] += minutos_campo(m, now)
    return sorted(out.values(), key=lambda r: r["empleado"].full_name)


# ---------------------------------------------------------------- panel («Configuración y mapa»)


def gps_personas(db: Session) -> dict[str, list[User]]:
    """K05 «¿Quién tiene GPS?»: asesores with Captación vs. the ones without."""
    us = list(
        db.scalars(
            select(User).where(User.is_active.is_(True), User.cargo == Cargo.ASESOR)
        ).unique()
    )
    con = sorted((u for u in us if perfil(u) == "asesor"), key=lambda u: u.full_name)
    sin = sorted(
        (u for u in us if has_commercial_activity(u) and not can_capture(u)),
        key=lambda u: u.full_name,
    )
    return {"con": con, "sin": sin}


def en_campo(db: Session, tipo: TipoMovimiento) -> tuple[list[Movimiento], Movimiento | None]:
    """Who is in the field now (open records), and the last finished one."""
    abiertos = list(
        db.scalars(
            select(Movimiento)
            .where(Movimiento.tipo == tipo, Movimiento.fin_at.is_(None))
            .order_by(Movimiento.ocurrido_at)
        ).unique()
    )
    ultimo = db.scalar(
        select(Movimiento)
        .where(Movimiento.tipo == tipo, Movimiento.fin_at.is_not(None))
        .order_by(Movimiento.fin_at.desc())
        .limit(1)
    )
    return abiertos, ultimo


def cambios_config(db: Session, limit: int = 5) -> list[MovimientoEvento]:
    return list(
        db.scalars(
            select(MovimientoEvento)
            .where(MovimientoEvento.tipo == TipoEventoMovimiento.CONFIG)
            .order_by(MovimientoEvento.created_at.desc())
            .limit(limit)
        ).unique()
    )


def historial(db: Session, m: Movimiento) -> list[MovimientoEvento]:
    return list(
        db.scalars(
            select(MovimientoEvento)
            .where(MovimientoEvento.movimiento_id == m.id)
            .order_by(MovimientoEvento.created_at)
        ).unique()
    )


# ---------------------------------------------------------------- rendimiento (G-036)


def descuentos(db: Session, user: User, start: datetime, end: datetime) -> list[dict[str, Any]]:
    """1 point per alert of the month that was rejected or expired without a justification."""
    if perfil(user) is None:
        return []
    cfg = get_config(db)
    now = fechas.now()
    rows = db.scalars(
        select(Movimiento).where(
            Movimiento.empleado_id == user.id,
            Movimiento.tipo.in_(tuple(ALERTAS_GPS)),
            Movimiento.estado.in_((E.RECHAZADA, E.SIN_JUSTIFICAR)),
            Movimiento.ocurrido_at >= start,
            Movimiento.ocurrido_at < end,
        )
    ).unique()
    out = []
    for m in sorted(rows, key=lambda x: x.ocurrido_at):
        if not descuenta(m, cfg, now):
            continue
        porque = (
            f"rechazada por {m.revisado_por.full_name}"
            if m.estado == E.RECHAZADA and m.revisado_por
            else "rechazada"
            if m.estado == E.RECHAZADA
            else "sin justificar en el plazo"
        )
        out.append(
            {
                "titulo": f"GPS: {TIPO_LABELS[m.tipo].lower()} {porque}",
                "detalle": f"{m.code} · {fechas.fmt(m.ocurrido_at)}",
                "puntos": DESCUENTO,
            }
        )
    return out


# ---------------------------------------------------------------- export


def export_csv(db: Session, viewer: User, f: Filtros) -> tuple[str, int]:
    """K05-ger «Descargar (Excel)»: CSV that Excel opens (with a BOM, so accents show)."""
    ensure_panel(viewer)
    rows, _ = listar(db, viewer, f)
    cfg, now = get_config(db), fechas.now()
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf)
    w.writerow(
        ["Código", "Fecha", "Hora", "Empleado", "Acción", "Detalle", "Duración", "Estado", "Revisó"]
    )
    for m in rows:
        local = m.ocurrido_at.astimezone(fechas.BOGOTA)
        est = "Sin justificar · vencida" if vencida(m, cfg, now) else ESTADO_LABELS[m.estado]
        w.writerow(
            [
                m.code,
                local.date().isoformat(),
                f"{local:%H:%M}",
                m.empleado.full_name,
                TIPO_LABELS[m.tipo],
                detalle_txt(db, m, now),
                "" if m.tipo in ALERTAS_GPS else fmt_dur(minutos_campo(m, now)),
                est,
                m.revisado_por.full_name if m.revisado_por else "",
            ]
        )
    _evento(
        db,
        None,
        TipoEventoMovimiento.DESCARGA,
        viewer,
        detalle=f"{len(rows)} filas · {f.desde.isoformat()} a {f.hasta.isoformat()}",
    )
    db.flush()
    return buf.getvalue(), len(rows)
