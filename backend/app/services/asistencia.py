"""Asistencia (prototypes Z04 «Mi asistencia», K17 «Asistencia y ausencias», X08 «Sedes,
ubicaciones y horarios»; decisions G-048, G-049, G-050, G-051).

* **Who marks**: asesores, Atención, the Coordinador and the Auxiliar (configurable per cargo;
  Gerencia off by default). One button: date, hour and location are recorded by themselves.
* **Where**: each person's assigned sede (default the main one; Coordinación changes it for
  asesores and Atención, the Auxiliar and Gerencia for everyone). Asesores with Captación whose
  accepted route has zones today mark in the zone of that time (Rutas). Inside the sede's radius
  (or the zone's radius around its center) = valid.
* **Preoperacional first**, when the person's cargo does it (G-007, «el preoperacional antes de
  marcar entrada»).
* **Entrada**: up to `limite_min` after the hour. Late 1…`leve_max` min = leve, more = grave; both
  are impuntualidad and the minutes are discounted from the salary. Outside the location (or
  without location) the person justifies («cambio solicitado» / «imprevisto»); Coordinación
  reviews (Gerencia for the Coordinador's and the Auxiliar's). Accepted = the marked hour counts.
  Rejected = «Marca entrada cuando estés en la sede o ubicación asignada»; until they do, it's
  impuntualidad (all day if they never do).
* **Salida**: before the hour needs a reason («imprevisto» / «permiso personal autorizado»),
  reviewed by Coordinación or the Auxiliar (Gerencia for theirs); rejected = the time not worked
  is discounted. `extra_min` or more after the hour = horas extra, which Coordinación AND the
  Auxiliar accept (Gerencia for theirs). Accepted horas extra go to Salarios (their value is
  PENDIENTE: contador).
* **Puntualidad** of «Mis resultados» is calculated here (same 1–5 scale as the preoperacional).
"""

from __future__ import annotations

import csv
import io
import math
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AsistenciaEvento,
    LiquidacionSalario,
    Marcacion,
    Novedad,
    SalarioConfig,
    Sede,
    UbicacionAsignada,
    User,
)
from app.models.enums import Cargo, EstadoNovedad, EstadoSalario
from app.services import configuracion, fechas
from app.services.errors import ConflictError, DomainError, NotFoundError, PermissionDeniedError

MOTIVOS_ENTRADA = {"cambio_solicitado": "Cambio solicitado", "imprevisto": "Imprevisto"}
MOTIVOS_SALIDA = {"imprevisto": "Imprevisto", "permiso": "Permiso personal autorizado"}
# Route zones have no address yet: example centers (PENDIENTE DE CONFIGURACIÓN)
ZONA_CENTROS: dict[str, tuple[float, float]] = {
    "Belén": (6.2306, -75.6036),
    "El Poblado": (6.2087, -75.5671),
    "Envigado": (6.1719, -75.5868),
    "Guayabal": (6.2117, -75.5850),
    "Laureles": (6.2447, -75.5961),
    "Sabaneta": (6.1515, -75.6166),
}
CARGOS_EQUIPO_COORD = (Cargo.ASESOR, Cargo.ATENCION_CLIENTE)
HORAS_DIA = 8  # to turn a day's pay into minutes (PENDIENTE: contador)


# ---------------------------------------------------------------- config & access


def cfg(db: Session) -> dict[str, Any]:
    return configuracion.get(db, "asistencia")


def marca(db: Session, u: User) -> bool:
    return u.is_active and bool(cfg(db)["marcan"].get(u.cargo.value, False))


def ve_equipo(u: User) -> bool:
    return u.is_active and u.cargo in (
        Cargo.COORDINACION,
        Cargo.AUXILIAR_ADMINISTRATIVA,
        Cargo.GERENCIA,
    )


def configura(u: User) -> bool:
    """G-050: the Auxiliar and Gerencia («Asistencia y puntualidad»)."""
    return u.is_active and u.cargo in (Cargo.AUXILIAR_ADMINISTRATIVA, Cargo.GERENCIA)


def en_equipo(viewer: User, u: User) -> bool:
    """Coordinación sees asesores and Atención; the Auxiliar and Gerencia, everyone."""
    if viewer.cargo == Cargo.COORDINACION:
        return u.cargo in CARGOS_EQUIPO_COORD
    return ve_equipo(viewer)


def _de_gerencia(u: User) -> bool:
    """The Coordinador's and the Auxiliar's reviews go to Gerencia (G-050)."""
    return u.cargo in (Cargo.COORDINACION, Cargo.AUXILIAR_ADMINISTRATIVA)


def revisa_entrada(viewer: User, u: User) -> bool:
    if viewer.id == u.id:
        return False
    if _de_gerencia(u):
        return viewer.cargo == Cargo.GERENCIA
    return viewer.cargo == Cargo.COORDINACION


def revisa_salida(viewer: User, u: User) -> bool:
    if viewer.id == u.id:
        return False
    if _de_gerencia(u):
        return viewer.cargo == Cargo.GERENCIA
    return viewer.cargo in (Cargo.COORDINACION, Cargo.AUXILIAR_ADMINISTRATIVA)


def quien_revisa(u: User) -> str:
    return "Gerencia" if _de_gerencia(u) else "Coordinación"


# ---------------------------------------------------------------- schedule


def _hm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def horario(db: Session, d: date) -> tuple[time, time] | None:
    """Company schedule of the day (G-048: Mon–Fri and Saturday; Sunday off)."""
    c = cfg(db)
    wd = d.isoweekday()
    if wd <= 5:
        return _hm(c["entrada_lv"]), _hm(c["salida_lv"])
    if wd == 6:
        return _hm(c["entrada_sab"]), _hm(c["salida_sab"])
    return None


def _dt(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=fechas.BOGOTA)


def _min(a: datetime, b: datetime) -> int:
    """Whole minutes from a to b (0 if b is before a)."""
    return max(0, int((b - a).total_seconds() // 60))


def _h12(t: time | datetime) -> str:
    if isinstance(t, datetime):
        t = t.astimezone(fechas.BOGOTA).time()
    h = t.hour % 12 or 12
    return f"{h}:{t.minute:02d} {'a. m.' if t.hour < 12 else 'p. m.'}"


def dur_txt(m: int) -> str:
    if m < 60:
        return f"{m} min"
    return f"{m // 60} h" + (f" {m % 60} min" if m % 60 else "")


def tipo_tarde(db: Session, minutos: int) -> str | None:
    if minutos <= 0:
        return None
    return "leve" if minutos <= cfg(db)["leve_max"] else "grave"


# ---------------------------------------------------------------- locations


def distancia_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6_371_000
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(x))


def km_txt(m: float) -> str:
    return f"{round(m)} m" if m < 1000 else f"{m / 1000:.1f} km".replace(".", ",")


def principal(db: Session) -> Sede | None:
    return db.scalar(select(Sede).where(Sede.activa, Sede.principal).limit(1)) or db.scalar(
        select(Sede).where(Sede.activa).order_by(Sede.created_at).limit(1)
    )


def sede_de(db: Session, u: User) -> Sede | None:
    ua = db.get(UbicacionAsignada, u.id)
    if ua is not None and ua.sede.activa:
        return ua.sede
    return principal(db)


@dataclass
class Lugar:
    """Where a person must mark right now."""

    txt: str  # «Oficina · Sede principal», «En ruta · Belén»
    detalle: str
    centro: tuple[float, float] | None
    radio: int
    nombre: str  # «Sede principal», «Belén»


def lugar(db: Session, u: User, cuando: datetime | None = None) -> Lugar:
    from app.services import rutas
    from app.services.policies import can_capture

    cuando = cuando or fechas.now()
    d = fechas.local_date(cuando)
    if can_capture(u):
        zs = rutas.zonas_del_dia(db, u, d)
        if zs:
            hora = cuando.astimezone(fechas.BOGOTA).time()
            z = next((z for z in zs if z.hora_inicio <= hora <= z.hora_fin), None) or next(
                (z for z in zs if hora < z.hora_inicio), zs[-1]
            )
            radio = int(cfg(db)["radio_zona_m"])
            return Lugar(
                f"En ruta · {z.zona}",
                f"Ruta del coordinador · {rutas._h(z.hora_inicio)}–{rutas._h(z.hora_fin)} · "
                f"radio de {km_txt(radio)} desde el centro de la zona",
                ZONA_CENTROS.get(z.zona),
                radio,
                z.zona,
            )
    s = sede_de(db, u)
    if s is None:
        return Lugar(
            "Sin sede registrada", "La Auxiliar administrativa registra las sedes", None, 0, "—"
        )
    pref = "Oficina · " if u.cargo == Cargo.ASESOR and u.funcion is None else ""
    ua = db.get(UbicacionAsignada, u.id)
    quien = (
        f"asignada por {ua.updated_by.full_name}"
        if ua and ua.updated_by
        else ("tu ubicación fija" if u.cargo == Cargo.COORDINACION else "ubicación por defecto")
    )
    return Lugar(
        f"{pref}{s.nombre}",
        f"{s.direccion} · radio de {s.radio_m} m · {quien}",
        (s.lat, s.lng),
        s.radio_m,
        s.nombre,
    )


def verificar(lug: Lugar, lat: float | None, lng: float | None) -> tuple[bool, str]:
    """(inside, «where it marked» text)."""
    if lat is None or lng is None:
        return False, "Sin ubicación ✕"
    if lug.centro is None:  # «Otra zona»: nothing to compare with
        return True, f"{lug.nombre} (sin verificar)"
    dist = distancia_m(lug.centro, (lat, lng))
    if dist <= lug.radio:
        return True, f"{lug.nombre} ✓"
    return False, f"A {km_txt(dist)} ✕"


# ---------------------------------------------------------------- records


def _evento(
    db: Session, m: Marcacion, actor: User | None, accion: str, antes=None, despues=None
) -> None:
    db.add(
        AsistenciaEvento(
            marcacion_id=m.id,
            user_id=m.user_id,
            registro=f"{m.user.full_name} · {m.fecha:%d/%m/%Y}",
            accion=accion,
            antes=None if antes is None else str(antes)[:300],
            despues=None if despues is None else str(despues)[:500],
            actor_id=actor.id if actor else None,
        )
    )


def de_hoy(db: Session, u: User, d: date | None = None) -> Marcacion | None:
    d = d or fechas.local_date(fechas.now())
    return db.scalar(select(Marcacion).where(Marcacion.user_id == u.id, Marcacion.fecha == d))


def _recalcular_salario(db: Session, m: Marcacion) -> None:
    """Pay periods not confirmed yet take the new minutes (as novedades do)."""
    from app.services import novedades

    corte = 1 if m.fecha.day <= 15 else 2
    liq = db.scalar(
        select(LiquidacionSalario).where(
            LiquidacionSalario.user_id == m.user_id,
            LiquidacionSalario.periodo == m.fecha.replace(day=1),
            LiquidacionSalario.corte == corte,
        )
    )
    c = db.get(SalarioConfig, m.user_id)
    if liq is not None and c is not None and liq.estado == EstadoSalario.POR_CONFIRMAR:
        novedades.aplicar(db, liq, c.salario_mensual)


@dataclass
class Resultado:
    ok: bool
    requiere_justificacion: bool = False
    titulo: str = ""
    detalle: str = ""
    opciones: dict[str, str] | None = None
    marcacion: Marcacion | None = None


def marcar_entrada(
    db: Session,
    u: User,
    *,
    lat: float | None,
    lng: float | None,
    motivo: str | None = None,
    texto: str | None = None,
) -> Resultado:
    if not marca(db, u):
        raise PermissionDeniedError("Tu cargo no marca entrada y salida.")
    now = fechas.now()
    hoy = fechas.local_date(now)
    h = horario(db, hoy)
    if h is None:
        raise DomainError("Hoy no hay jornada: no se marca entrada.")
    c = cfg(db)
    if c["exigir_preoperacional"]:
        from app.services import preoperacional

        if preoperacional.activo_para(db, u) and preoperacional.get_de_hoy(db, u) is None:
            raise DomainError("Primero haz tu preoperacional de hoy: después marcas la entrada.")
    m = de_hoy(db, u, hoy)
    re_marca = m is not None and m.entrada_estado == "rechazada"
    if m is not None and m.entrada_at is not None and not re_marca:
        raise ConflictError("Ya marcaste la entrada hoy.")
    inicio = _dt(hoy, h[0])
    if not re_marca and now > inicio + timedelta(minutes=c["limite_min"]):
        raise DomainError(
            "Ya pasó el límite para marcar entrada "
            f"({_h12(inicio + timedelta(minutes=c['limite_min']))}). "
            "Habla con Coordinación: el día queda sin entrada."
        )
    if now > _dt(hoy, h[1]):
        raise DomainError("La jornada de hoy ya terminó.")
    lug = lugar(db, u, now)
    dentro, donde = verificar(lug, lat, lng)
    if not dentro:
        if motivo not in MOTIVOS_ENTRADA or len((texto or "").strip()) < 5:
            return Resultado(
                False,
                True,
                "Estás fuera de tu sede o ubicación asignada"
                if lat is not None
                else "No pudimos obtener tu ubicación",
                f"Tu ubicación asignada es «{lug.txt}». Justifica y envía; "
                f"{quien_revisa(u)} la revisa.",
                MOTIVOS_ENTRADA,
            )
    if m is None:
        m = Marcacion(user_id=u.id, fecha=hoy, asignada=lug.txt)
        m.user = u
        db.add(m)
    antes = "Rechazada" if re_marca else None
    m.asignada = lug.txt
    m.entrada_at, m.entrada_lat, m.entrada_lng = now, lat, lng
    m.entrada_lugar, m.entrada_dentro = donde, dentro
    m.minutos_tarde = _min(inicio, now)
    if dentro:
        m.entrada_estado = "impuntual" if m.minutos_tarde else "a_tiempo"
        m.entrada_motivo = m.entrada_texto = None
    else:
        m.entrada_estado = "por_aprobar"
        m.entrada_motivo, m.entrada_texto = motivo, (texto or "").strip()[:500]
    m.entrada_revisada_por_id = m.entrada_revisada_at = None
    db.flush()
    _evento(
        db,
        m,
        u,
        "Marcó entrada de nuevo" if re_marca else "Marcó entrada",
        antes,
        f"{_h12(now)} · {donde} · {estado_entrada(db, m)[0]}"
        + (f" · {MOTIVOS_ENTRADA[motivo]}: «{m.entrada_texto}»" if not dentro else ""),
    )
    _recalcular_salario(db, m)
    db.flush()
    return Resultado(True, marcacion=m)


def marcar_salida(
    db: Session,
    u: User,
    *,
    lat: float | None,
    lng: float | None,
    motivo: str | None = None,
    texto: str | None = None,
) -> Resultado:
    if not marca(db, u):
        raise PermissionDeniedError("Tu cargo no marca entrada y salida.")
    now = fechas.now()
    hoy = fechas.local_date(now)
    m = de_hoy(db, u, hoy)
    if m is None or m.entrada_at is None or m.entrada_estado == "rechazada":
        raise DomainError("Primero marca la entrada.")
    if m.salida_at is not None:
        raise ConflictError("Ya marcaste la salida hoy.")
    h = horario(db, hoy)
    fin = _dt(hoy, h[1]) if h else now
    c = cfg(db)
    antes, extra = _min(now, fin), _min(fin, now)
    texto = (texto or "").strip()
    if antes > 0:
        if motivo not in MOTIVOS_SALIDA or len(texto) < 5:
            return Resultado(
                False,
                True,
                f"Estás saliendo antes de tu hora ({_h12(fin)})",
                "Elige el motivo, justifica y envía; "
                + (
                    "Gerencia la revisa."
                    if _de_gerencia(u)
                    else "Coordinación o la Auxiliar la revisan."
                ),
                MOTIVOS_SALIDA,
            )
        m.salida_tipo, m.salida_estado, m.minutos_antes = "anticipada", "por_aprobar", antes
        m.salida_motivo, m.salida_texto = motivo, texto[:500]
    elif extra >= c["extra_min"]:
        m.salida_tipo, m.salida_estado, m.minutos_extra = "extra", "por_aprobar", extra
        m.salida_texto = texto[:500] or None
    else:
        m.salida_tipo, m.salida_estado = "marcada", "ok"
    m.salida_at, m.salida_lat, m.salida_lng = now, lat, lng
    _evento(db, m, u, "Marcó salida", None, f"{_h12(now)} · {estado_salida(m)[0]}")
    _recalcular_salario(db, m)
    db.flush()
    return Resultado(True, marcacion=m)


def get(db: Session, viewer: User, id_: uuid.UUID) -> Marcacion:
    m = db.get(Marcacion, id_)
    if m is None or not (m.user_id == viewer.id or en_equipo(viewer, m.user)):
        raise NotFoundError("Ese registro no existe.")
    return m


def revisar(db: Session, m: Marcacion, que: str, acepta: bool, *, actor: User) -> Marcacion:
    """que: entrada · salida (early exit) · extra (horas extra)."""
    u = m.user
    if que == "entrada":
        if not revisa_entrada(actor, u):
            raise PermissionDeniedError(f"Esta justificación la revisa {quien_revisa(u)}.")
        if m.entrada_estado != "por_aprobar":
            raise ConflictError("Esa entrada ya no está por aprobar.")
        m.entrada_estado = "aceptada" if acepta else "rechazada"
        m.entrada_revisada_por_id, m.entrada_revisada_at = actor.id, fechas.now()
        accion = (
            "Aceptó la entrada fuera de ubicación"
            if acepta
            else "Rechazó la entrada fuera de ubicación"
        )
    elif que in ("salida", "extra"):
        if not revisa_salida(actor, u):
            raise PermissionDeniedError(
                "Esto lo revisa "
                + ("Gerencia." if _de_gerencia(u) else "Coordinación o la Auxiliar.")
            )
        tipo = "anticipada" if que == "salida" else "extra"
        if m.salida_tipo != tipo or m.salida_estado != "por_aprobar":
            raise ConflictError("Eso ya no está por aprobar.")
        if tipo == "anticipada" or _de_gerencia(u):
            m.salida_estado = "aceptada" if acepta else "rechazada"
            if tipo == "extra":
                m.extra_coord = m.extra_aux = acepta
        else:  # horas extra of asesores and Atención: Coordinación AND the Auxiliar
            campo = "extra_coord" if actor.cargo == Cargo.COORDINACION else "extra_aux"
            if getattr(m, campo) is not None:
                raise ConflictError("Ya respondiste.")
            setattr(m, campo, acepta)
            if m.extra_coord is False or m.extra_aux is False:
                m.salida_estado = "rechazada"
            elif m.extra_coord and m.extra_aux:
                m.salida_estado = "aceptada"
        m.salida_revisada_por_id = actor.id
        accion = (
            ("Aceptó la salida anticipada" if acepta else "Rechazó la salida anticipada")
            if tipo == "anticipada"
            else ("Aceptó las horas extra" if acepta else "No aceptó las horas extra")
        )
    else:
        raise DomainError("¿Qué se revisa?")
    _evento(db, m, actor, accion, "Por aprobar", None)
    _recalcular_salario(db, m)
    db.flush()
    return m


# ---------------------------------------------------------------- what each record means


def minutos_descuento(db: Session, m: Marcacion, *, ahora: datetime | None = None) -> int:
    """Impuntualidad + rejected early exit. A rejected entrada never marked again counts until the
    end of the day (G-048: «hasta que la registre se considera impuntualidad»)."""
    total = 0
    h = horario(db, m.fecha)
    if m.entrada_estado in ("impuntual", "aceptada"):
        total += m.minutos_tarde
    elif m.entrada_estado == "rechazada" and h:
        ahora = ahora or fechas.now()
        fin = min(_dt(m.fecha, h[1]), ahora)
        total += _min(_dt(m.fecha, h[0]), fin)
    if m.salida_tipo == "anticipada" and m.salida_estado == "rechazada":
        total += m.minutos_antes
    return total


def extra_aceptada(m: Marcacion) -> int:
    return m.minutos_extra if m.salida_tipo == "extra" and m.salida_estado == "aceptada" else 0


def estado_entrada(db: Session, m: Marcacion | None) -> tuple[str, str]:
    if m is None or m.entrada_estado is None:
        return "Sin marcar", "gray"
    t = tipo_tarde(db, m.minutos_tarde)
    tarde = f" · {t} · {m.minutos_tarde} min" if t else ""
    return {
        "a_tiempo": ("A tiempo", "ok"),
        "impuntual": (f"Impuntual{tarde}", "warn"),
        "por_aprobar": ("Por aprobar", "warn"),
        "aceptada": (f"Fuera de ubicación · aceptada{tarde}", "info"),
        "rechazada": ("Rechazada · marca de nuevo", "bad"),
    }[m.entrada_estado]


def estado_salida(m: Marcacion | None) -> tuple[str, str]:
    if m is None or m.salida_at is None:
        return "Sin marcar", "gray"
    if m.salida_tipo == "marcada":
        return "Marcada", "ok"
    if m.salida_tipo == "anticipada":
        e = {
            "por_aprobar": "En revisión",
            "aceptada": "Anticipada · aceptada",
            "rechazada": "Anticipada · rechazada",
        }
        return f"{e[m.salida_estado]} · {dur_txt(m.minutos_antes)} antes", {
            "por_aprobar": "warn",
            "aceptada": "ok",
            "rechazada": "bad",
        }[m.salida_estado]
    e = {
        "por_aprobar": "Horas extra en revisión",
        "aceptada": "Horas extra aceptadas",
        "rechazada": "Horas extra no aceptadas",
    }
    return f"{e[m.salida_estado]} · {dur_txt(m.minutos_extra)}", {
        "por_aprobar": "warn",
        "aceptada": "info",
        "rechazada": "gray",
    }[m.salida_estado]


def _obs(db: Session, m: Marcacion) -> str:
    out = []
    d = minutos_descuento(db, m)
    if m.entrada_motivo:
        rev = (
            "aceptado"
            if m.entrada_estado == "aceptada"
            else ("rechazado" if m.entrada_estado == "rechazada" else "por revisar")
        )
        out.append(f"{MOTIVOS_ENTRADA[m.entrada_motivo]} {rev}")
    if m.salida_motivo:
        out.append(f"Salida antes: {MOTIVOS_SALIDA[m.salida_motivo].lower()}")
    if extra_aceptada(m):
        out.append(f"{dur_txt(m.minutos_extra)} extra aceptada")
    if d:
        out.append(f"{dur_txt(d)} se descuentan del salario")
    return " · ".join(out)


def fila(db: Session, m: Marcacion, viewer: User | None = None) -> dict[str, Any]:
    ee, ec = estado_entrada(db, m)
    se, sc = estado_salida(m)
    return {
        "id": m.id,
        "user_id": m.user_id,
        "nombre": m.user.full_name,
        "fecha": m.fecha,
        "asignada": m.asignada,
        "entrada": _h12(m.entrada_at) if m.entrada_at else None,
        "entrada_lugar": m.entrada_lugar,
        "entrada_estado": m.entrada_estado,
        "entrada_txt": ee,
        "entrada_cls": ec,
        "minutos_tarde": m.minutos_tarde,
        "tipo_tarde": tipo_tarde(db, m.minutos_tarde)
        if m.entrada_estado in ("impuntual", "aceptada")
        else None,
        "salida": _h12(m.salida_at) if m.salida_at else None,
        "salida_tipo": m.salida_tipo,
        "salida_estado": m.salida_estado,
        "salida_txt": se,
        "salida_cls": sc,
        "minutos_descuento": minutos_descuento(db, m),
        "minutos_extra": extra_aceptada(m),
        "observacion": _obs(db, m),
    }


# ---------------------------------------------------------------- views


def puntualidad(db: Session, u: User, d1: date, d2: date) -> dict[str, Any]:
    """«Puntualidad de octubre» (Z04) and the automatic 1–5 rating of «Mis resultados» (G-051):
    days on time over days with entrada, on the preoperacional's scale."""
    from app.services import preoperacional

    ms = list(
        db.scalars(
            select(Marcacion).where(
                Marcacion.user_id == u.id,
                Marcacion.fecha >= d1,
                Marcacion.fecha <= d2,
                Marcacion.entrada_estado.is_not(None),
            )
        ).unique()
    )
    leves = sum(
        1
        for m in ms
        if m.entrada_estado in ("impuntual", "aceptada")
        and tipo_tarde(db, m.minutos_tarde) == "leve"
    )
    graves = sum(
        1
        for m in ms
        if m.entrada_estado in ("impuntual", "aceptada")
        and tipo_tarde(db, m.minutos_tarde) == "grave"
    )
    rech = sum(1 for m in ms if m.entrada_estado == "rechazada")
    a_tiempo = sum(
        1
        for m in ms
        if m.entrada_estado in ("a_tiempo",)
        or (m.entrada_estado == "aceptada" and not m.minutos_tarde)
    )
    decididos = [m for m in ms if m.entrada_estado != "por_aprobar"]
    partes = [
        f"{leves} leve{'s' if leves != 1 else ''}" if leves else "",
        f"{graves} grave{'s' if graves != 1 else ''}" if graves else "",
        f"{rech} rechazada{'s' if rech != 1 else ''}" if rech else "",
    ]
    txt = " · ".join(p for p in partes if p) or (
        "Sin impuntualidades" if ms else "Sin marcaciones todavía"
    )
    pct = round(100 * a_tiempo / len(decididos)) if decididos else None
    return {
        "txt": txt,
        "dias": len(ms),
        "a_tiempo": a_tiempo,
        "pct": pct,
        "puntaje": preoperacional.puntaje(pct) if pct is not None else None,
        "minutos": sum(minutos_descuento(db, m) for m in ms),
    }


def mia(db: Session, u: User) -> dict[str, Any]:
    now = fechas.now()
    hoy = fechas.local_date(now)
    c = cfg(db)
    h = horario(db, hoy)
    m = de_hoy(db, u, hoy)
    lug = lugar(db, u, now)
    p1 = hoy.replace(day=1)
    reg = list(
        db.scalars(
            select(Marcacion)
            .where(Marcacion.user_id == u.id, Marcacion.fecha >= hoy - timedelta(days=30))
            .where(Marcacion.fecha < hoy)
            .order_by(Marcacion.fecha.desc())
        ).unique()
    )
    preop_pend = False
    if c["exigir_preoperacional"]:
        from app.services import preoperacional

        preop_pend = preoperacional.activo_para(db, u) and preoperacional.get_de_hoy(db, u) is None
    limite = _dt(hoy, h[0]) + timedelta(minutes=c["limite_min"]) if h else None
    fin = _dt(hoy, h[1]) if h else None
    ee, ec = estado_entrada(db, m)
    se, sc = estado_salida(m)
    puede_e = (
        bool(h)
        and marca(db, u)
        and (m is None or m.entrada_at is None or m.entrada_estado == "rechazada")
        and now <= fin
        and ((m is not None and m.entrada_estado == "rechazada") or now <= limite)
    )
    puede_s = bool(m and m.entrada_at and m.entrada_estado != "rechazada" and m.salida_at is None)
    recordar = bool(
        puede_s
        and fin
        and fin - timedelta(minutes=c["recordatorio_min"]) <= now <= fin + timedelta(hours=2)
    )
    return {
        "marca": marca(db, u),
        "quien": f"{u.full_name}",
        "revisa": quien_revisa(u),
        "fecha": hoy,
        "horario_hoy": f"{_h12(h[0])} – {_h12(h[1])}" if h else "Hoy no hay jornada",
        "horario_txt": f"Lun a vie {_h12(_hm(c['entrada_lv']))}–{_h12(_hm(c['salida_lv']))} · "
        f"sáb {_h12(_hm(c['entrada_sab']))}–{_h12(_hm(c['salida_sab']))} · "
        "lo configura la Auxiliar administrativa",
        "ubicacion": lug.txt,
        "ubicacion_det": lug.detalle,
        "puntualidad": puntualidad(db, u, p1, hoy),
        "mes": fechas._MESES[hoy.month - 1],
        "hoy": fila(db, m) if m else None,
        "entrada_txt": ee,
        "entrada_cls": ec,
        "salida_txt": se,
        "salida_cls": sc,
        "puede_entrada": puede_e,
        "puede_salida": puede_s,
        "preop_pendiente": preop_pend and (m is None or m.entrada_at is None),
        "limite": _h12(limite) if limite else None,
        "fin": _h12(fin) if fin else None,
        "pasado_limite": bool(limite and now > limite and (m is None or m.entrada_at is None)),
        "recordar_salida": recordar,
        "registro": [fila(db, x) for x in reg],
        "motivos_entrada": MOTIVOS_ENTRADA,
        "motivos_salida": MOTIVOS_SALIDA,
    }


def personas(db: Session, viewer: User) -> list[User]:
    us = db.scalars(select(User).where(User.is_active).order_by(User.full_name)).unique()
    return [u for u in us if marca(db, u) and en_equipo(viewer, u) and u.id != viewer.id] + (
        [viewer] if marca(db, viewer) and viewer.cargo != Cargo.COORDINACION else []
    )


def _ausencias(db: Session, ids: list[uuid.UUID], d: date) -> dict[uuid.UUID, str]:
    from app.services.novedades import TIPO_LABELS

    rows = db.scalars(
        select(Novedad).where(
            Novedad.empleado_id.in_(ids),
            Novedad.estado == EstadoNovedad.REGISTRADA,
            Novedad.desde <= d,
            Novedad.hasta >= d,
        )
    ).unique()
    return {n.empleado_id: TIPO_LABELS[n.tipo] for n in rows}


def _acciones(viewer: User, m: Marcacion) -> list[dict[str, Any]]:
    """What this viewer can review on this record (K17 «Por aprobar»)."""
    u = m.user
    out = []
    if m.entrada_estado == "por_aprobar":
        out.append(
            {
                "que": "entrada",
                "tipo": "Entrada fuera de ubicación",
                "tcls": "bad",
                "detalle": f"Marcó {_h12(m.entrada_at)} en {m.entrada_lugar.replace(' ✕', '')} · "
                f"ubicación asignada: {m.asignada}",
                "justificacion": f"{MOTIVOS_ENTRADA.get(m.entrada_motivo or '', '')}: "
                f"«{m.entrada_texto}»",
                "puede": revisa_entrada(viewer, u),
                "quien": f"La aprueba {quien_revisa(u)}.",
                "estado": "Pendiente",
            }
        )
    if m.salida_tipo == "anticipada" and m.salida_estado == "por_aprobar":
        out.append(
            {
                "que": "salida",
                "tipo": "Salida anticipada",
                "tcls": "warn",
                "detalle": f"Marcó salida {_h12(m.salida_at)} · "
                f"{dur_txt(m.minutos_antes)} antes del horario",
                "justificacion": f"{MOTIVOS_SALIDA.get(m.salida_motivo or '', '')}: "
                f"«{m.salida_texto}»",
                "puede": revisa_salida(viewer, u),
                "quien": "La aprueba "
                + (
                    "Gerencia." if _de_gerencia(u) else "Coordinación o la Auxiliar administrativa."
                ),
                "estado": "Pendiente",
            }
        )
    if m.salida_tipo == "extra" and m.salida_estado == "por_aprobar":
        doble = not _de_gerencia(u)
        mio = (
            ("extra_coord" if viewer.cargo == Cargo.COORDINACION else "extra_aux")
            if viewer.cargo in (Cargo.COORDINACION, Cargo.AUXILIAR_ADMINISTRATIVA) and doble
            else None
        )
        lbl = lambda v: "pendiente" if v is None else ("aceptó" if v else "no aceptó")  # noqa: E731
        out.append(
            {
                "que": "extra",
                "tipo": "Horas extra",
                "tcls": "info",
                "detalle": f"Marcó salida {_h12(m.salida_at)} · {dur_txt(m.minutos_extra)} "
                f"después del horario ({m.fecha:%d/%m})",
                "justificacion": f"Observación: «{m.salida_texto}»"
                if m.salida_texto
                else "Sin observación",
                "puede": revisa_salida(viewer, u)
                and (not doble or (mio is not None and getattr(m, mio) is None)),
                "quien": (
                    "Las aceptan Coordinación y la Auxiliar administrativa."
                    if doble
                    else "Las acepta Gerencia."
                )
                + (" Ya respondiste." if mio and getattr(m, mio) is not None else ""),
                "estado": f"Coordinación: {lbl(m.extra_coord)} · Auxiliar: {lbl(m.extra_aux)}"
                if doble
                else "Pendiente",
            }
        )
    return out


def equipo(db: Session, viewer: User, d1: date, d2: date) -> dict[str, Any]:
    if not ve_equipo(viewer):
        raise PermissionDeniedError(
            "La asistencia del equipo la ven Coordinación, la Auxiliar y Gerencia."
        )
    if d1 > d2:
        raise DomainError("La fecha «Desde» no puede ser posterior a «Hasta».")
    now = fechas.now()
    hoy = fechas.local_date(now)
    gente = [
        u for u in personas(db, viewer) if u.id != viewer.id or viewer.cargo != Cargo.COORDINACION
    ]
    ids = [u.id for u in gente]
    hoy_m = {
        m.user_id: m
        for m in db.scalars(
            select(Marcacion).where(Marcacion.fecha == hoy, Marcacion.user_id.in_(ids))
        ).unique()
    }
    aus = _ausencias(db, ids, hoy)
    h = horario(db, hoy)
    limite_pasado = bool(h and now > _dt(hoy, h[0]) + timedelta(minutes=cfg(db)["limite_min"]))
    filas_hoy = []
    for u in gente:
        m = hoy_m.get(u.id)
        if m is None:
            if u.id in aus:
                e, cls = f"Ausencia · {aus[u.id].lower()}", "info"
            elif h is None:
                e, cls = "Sin jornada hoy", "gray"
            else:
                e, cls = (
                    ("Sin marcar · impuntualidad", "bad")
                    if limite_pasado
                    else ("Sin marcar", "gray")
                )
            filas_hoy.append(
                {
                    "user_id": u.id,
                    "nombre": u.full_name,
                    "asignada": lugar(db, u, now).txt,
                    "donde": "—",
                    "entrada": "—",
                    "estado": e,
                    "cls": cls,
                    "salida": "—",
                }
            )
        else:
            f = fila(db, m)
            filas_hoy.append(
                {
                    "user_id": u.id,
                    "nombre": u.full_name,
                    "asignada": m.asignada,
                    "donde": m.entrada_lugar or "—",
                    "entrada": f["entrada"] or "—",
                    "estado": f["entrada_txt"],
                    "cls": f["entrada_cls"],
                    "salida": f["salida"] and f"{f['salida']} · {f['salida_txt']}" or "—",
                }
            )
    rango = list(
        db.scalars(
            select(Marcacion)
            .where(Marcacion.fecha >= d1, Marcacion.fecha <= d2, Marcacion.user_id.in_(ids))
            .order_by(Marcacion.fecha.desc())
        ).unique()
    )
    pend_q = select(Marcacion).where(
        Marcacion.user_id.in_(ids), Marcacion.fecha >= hoy - timedelta(days=45)
    )
    pend = []
    for m in db.scalars(pend_q.order_by(Marcacion.fecha.desc())).unique():
        for a in _acciones(viewer, m):
            pend.append(
                a
                | {
                    "id": m.id,
                    "nombre": f"{m.user.full_name} · {CARGO_TXT.get(m.user.cargo, '')}",
                    "fecha": m.fecha,
                }
            )
    leves = sum(
        1
        for m in rango
        if m.entrada_estado in ("impuntual", "aceptada")
        and tipo_tarde(db, m.minutos_tarde) == "leve"
    )
    graves = sum(
        1
        for m in rango
        if m.entrada_estado in ("impuntual", "aceptada")
        and tipo_tarde(db, m.minutos_tarde) == "grave"
    )
    marcaron = sum(1 for u in gente if u.id in hoy_m and hoy_m[u.id].entrada_at)
    faltan = [u.full_name.split()[0] for u in gente if u.id not in hoy_m and u.id not in aus]
    return {
        "desde": d1,
        "hasta": d2,
        "hoy": hoy,
        "entrada_hoy": _h12(h[0]) if h else None,
        "kpis": {
            "marcaron": marcaron,
            "total": len(gente) - len([u for u in gente if u.id in aus and u.id not in hoy_m]),
            "faltan": faltan,
            "por_aprobar": sum(1 for p in pend if p["puede"]),
            "pendientes": len(pend),
            "leves": leves,
            "graves": graves,
            "minutos": sum(minutos_descuento(db, m) for m in rango),
            "extra": sum(extra_aceptada(m) for m in rango),
        },
        "por_aprobar": pend,
        "filas_hoy": filas_hoy,
        "registro": [fila(db, m) for m in rango],
        "puede_descargar": configura(viewer),
        "rol": viewer.cargo.value,
    }


CARGO_TXT = {
    Cargo.ASESOR: "Asesor",
    Cargo.ATENCION_CLIENTE: "Atención",
    Cargo.COORDINACION: "Coordinación",
    Cargo.AUXILIAR_ADMINISTRATIVA: "Auxiliar",
    Cargo.GERENCIA: "Gerencia",
}


def export_csv(db: Session, viewer: User, d1: date, d2: date) -> str:
    """K17 «Descargar Excel» (the Auxiliar and Gerencia): one row per person and day."""
    if not configura(viewer):
        raise PermissionDeniedError("El Excel lo descargan la Auxiliar y Gerencia.")
    data = equipo(db, viewer, d1, d2)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(
        [
            "Persona",
            "Fecha",
            "Ubicación asignada",
            "Dónde marcó",
            "Entrada",
            "Estado de entrada",
            "Minutos tarde",
            "Leve o grave",
            "Salida",
            "Estado de salida",
            "Minutos que se descuentan",
            "Horas extra aceptadas (min)",
            "Observación",
        ]
    )
    for r in data["registro"]:
        m = db.get(Marcacion, r["id"])
        w.writerow(
            [
                r["nombre"],
                r["fecha"].isoformat(),
                r["asignada"],
                m.entrada_lugar or "",
                r["entrada"] or "",
                r["entrada_txt"],
                r["minutos_tarde"],
                r["tipo_tarde"] or "",
                r["salida"] or "",
                r["salida_txt"],
                r["minutos_descuento"],
                r["minutos_extra"],
                r["observacion"],
            ]
        )
    return "﻿" + buf.getvalue()


# ---------------------------------------------------------------- settings, sedes, assignment


def config_vista(db: Session, viewer: User) -> dict[str, Any]:
    if not ve_equipo(viewer):
        raise PermissionDeniedError("Esto lo ven Coordinación, la Auxiliar y Gerencia.")
    sedes = list(db.scalars(select(Sede).order_by(Sede.principal.desc(), Sede.nombre)))
    uas = {x.user_id: x for x in db.scalars(select(UbicacionAsignada)).unique()}
    gente = [
        u
        for u in db.scalars(
            select(User).where(User.is_active).order_by(User.cargo, User.full_name)
        ).unique()
        if marca(db, u)
    ]
    return {
        "config": cfg(db),
        "puede_editar": configura(viewer),
        "sedes": [
            {
                "id": s.id,
                "nombre": s.nombre,
                "direccion": s.direccion,
                "lat": s.lat,
                "lng": s.lng,
                "radio_m": s.radio_m,
                "principal": s.principal,
                "activa": s.activa,
                "personas": sum(
                    1
                    for u in gente
                    if (
                        uas[u.id].sede_id
                        if u.id in uas
                        else (principal(db).id if principal(db) else None)
                    )
                    == s.id
                ),
            }
            for s in sedes
        ],
        "personas": [
            {
                "id": u.id,
                "nombre": u.full_name,
                "cargo": u.cargo.value,
                "sede_id": uas[u.id].sede_id if u.id in uas else None,
                "ubicacion": lugar(db, u).txt,
                "cambio": (
                    f"{uas[u.id].updated_by.full_name if uas[u.id].updated_by else '—'} · "
                    f"{fechas.fmt(uas[u.id].updated_at)}"
                )
                if u.id in uas
                else None,
                "puede_cambiar": puede_asignar(viewer, u),
            }
            for u in gente
        ],
        "cargos": {c.value: CARGO_TXT[c] for c in Cargo},
    }


def guardar_config(db: Session, valores: dict[str, Any], *, actor: User) -> dict[str, Any]:
    if not configura(actor):
        raise PermissionDeniedError(
            "El horario y las reglas los configuran la Auxiliar y Gerencia."
        )
    cur = cfg(db)
    if extra := set(valores) - set(cur):
        raise DomainError(f"No existe el valor «{sorted(extra)[0]}».")
    new = cur | valores
    try:
        hs = {k: _hm(new[k]) for k in ("entrada_lv", "salida_lv", "entrada_sab", "salida_sab")}
    except (ValueError, AttributeError) as e:
        raise DomainError("Revisa las horas del horario.") from e
    if hs["salida_lv"] <= hs["entrada_lv"] or hs["salida_sab"] <= hs["entrada_sab"]:
        raise DomainError("La salida debe ser después de la entrada.")
    if new["limite_min"] not in (15, 30, 45, 60):
        raise DomainError("El límite para marcar entrada es 15, 30, 45 o 60 minutos.")
    if new["leve_max"] not in (5, 10, 15) or new["leve_max"] >= new["limite_min"]:
        raise DomainError(
            "La impuntualidad leve va hasta 5, 10 o 15 minutos y debe ser menor que el límite."
        )
    if not 0 <= int(new["recordatorio_min"]) <= 30 or not 5 <= int(new["extra_min"]) <= 120:
        raise DomainError(
            "Revisa el recordatorio de salida y desde cuándo cuentan las horas extra."
        )
    if not 200 <= int(new["radio_zona_m"]) <= 10_000:
        raise DomainError("El radio de las zonas de ruta va de 200 m a 10 km.")
    marcan = new["marcan"]
    if set(marcan) != {c.value for c in Cargo} or not all(
        isinstance(v, bool) for v in marcan.values()
    ):
        raise DomainError("Revisa quién marca entrada y salida.")
    new["exigir_preoperacional"] = bool(new["exigir_preoperacional"])
    return configuracion._save(db, "asistencia", new, actor)


def _sede_datos(data: dict[str, Any]) -> dict[str, Any]:
    nombre, direccion = (data.get("nombre") or "").strip(), (data.get("direccion") or "").strip()
    if len(nombre) < 2 or len(direccion) < 5:
        raise DomainError("Escribe el nombre y la dirección de la sede.")
    try:
        lat, lng = float(data["lat"]), float(data["lng"])
    except (KeyError, TypeError, ValueError) as e:
        raise DomainError(
            "Falta la ubicación de la sede: usa «Tomar mi ubicación» estando allí, "
            "o escribe las coordenadas."
        ) from e
    if not (-5 <= lat <= 14 and -82 <= lng <= -66):
        raise DomainError("Esas coordenadas no están en Colombia.")
    radio = int(data.get("radio_m") or 100)
    if radio not in (50, 100, 200):
        raise DomainError("El radio es de 50, 100 o 200 m.")
    return {
        "nombre": nombre[:120],
        "direccion": direccion[:300],
        "lat": lat,
        "lng": lng,
        "radio_m": radio,
    }


def crear_sede(db: Session, data: dict[str, Any], *, actor: User) -> Sede:
    if not configura(actor):
        raise PermissionDeniedError("Las sedes las registran la Auxiliar y Gerencia.")
    d = _sede_datos(data)
    if db.scalar(select(Sede.id).where(Sede.nombre.ilike(d["nombre"]), Sede.activa)):
        raise ConflictError("Ya existe una sede con ese nombre.")
    s = Sede(**d, principal=principal(db) is None, created_by_id=actor.id)
    db.add(s)
    db.flush()
    db.add(
        AsistenciaEvento(
            registro=s.nombre,
            accion="Agregó la sede",
            despues=f"{s.direccion} · radio {s.radio_m} m",
            actor_id=actor.id,
        )
    )
    db.flush()
    return s


def editar_sede(db: Session, s: Sede, data: dict[str, Any], *, actor: User) -> Sede:
    if not configura(actor):
        raise PermissionDeniedError("Las sedes las registran la Auxiliar y Gerencia.")
    if "activa" in data and not data["activa"]:
        if s.principal:
            raise ConflictError(
                "La sede principal no se desactiva: marca otra como principal primero."
            )
        s.activa = False
        db.add(AsistenciaEvento(registro=s.nombre, accion="Desactivó la sede", actor_id=actor.id))
    elif data.get("principal"):
        for o in db.scalars(select(Sede).where(Sede.principal)):
            o.principal = False
        s.principal, s.activa = True, True
        db.add(
            AsistenciaEvento(registro=s.nombre, accion="Marcó la sede principal", actor_id=actor.id)
        )
    else:
        d = _sede_datos(
            {
                "nombre": s.nombre,
                "direccion": s.direccion,
                "lat": s.lat,
                "lng": s.lng,
                "radio_m": s.radio_m,
            }
            | data
        )
        antes = f"{s.direccion} · radio {s.radio_m} m"
        for k, v in d.items():
            setattr(s, k, v)
        db.add(
            AsistenciaEvento(
                registro=s.nombre,
                accion="Cambió la sede",
                antes=antes,
                despues=f"{s.direccion} · radio {s.radio_m} m",
                actor_id=actor.id,
            )
        )
    db.flush()
    return s


def puede_asignar(viewer: User, u: User) -> bool:
    """G-048: the Auxiliar and Gerencia, everyone; Coordinación, asesores and Atención."""
    if configura(viewer):
        return True
    return viewer.cargo == Cargo.COORDINACION and u.cargo in CARGOS_EQUIPO_COORD


def asignar(db: Session, u: User, sede_id: uuid.UUID, *, actor: User) -> UbicacionAsignada:
    if not puede_asignar(actor, u):
        raise PermissionDeniedError("No cambias la ubicación de esta persona.")
    s = db.get(Sede, sede_id)
    if s is None or not s.activa:
        raise NotFoundError("Esa sede no existe.")
    ua = db.get(UbicacionAsignada, u.id)
    antes = ua.sede.nombre if ua else (principal(db).nombre if principal(db) else None)
    if ua is None:
        ua = UbicacionAsignada(user_id=u.id, sede_id=s.id)
        db.add(ua)
    ua.sede_id, ua.updated_by_id = s.id, actor.id
    ua.updated_at = fechas.now()
    db.add(
        AsistenciaEvento(
            user_id=u.id,
            registro=u.full_name,
            accion="Cambió la ubicación asignada",
            antes=antes,
            despues=s.nombre,
            actor_id=actor.id,
        )
    )
    db.flush()
    db.refresh(ua)
    return ua


# ---------------------------------------------------------------- for other modules


def para_salario(db: Session, user_id: uuid.UUID, d1: date, d2: date) -> tuple[int, int]:
    """(minutes to discount, accepted extra minutes) in a pay period."""
    ms = db.scalars(
        select(Marcacion).where(
            Marcacion.user_id == user_id, Marcacion.fecha >= d1, Marcacion.fecha <= d2
        )
    ).unique()
    desc = extra = 0
    for m in ms:
        desc += minutos_descuento(db, m)
        extra += extra_aceptada(m)
    return desc, extra
