"""Rutas (prototypes X08 «Rutas y ubicación del equipo» and M04 «Mi ruta»; decisions G-083, G-051,
G-002/Etapa 3).

* **Coordinación** programs the routes: one by one or with the Excel template (here a CSV that
  Excel opens), and in «Rutas asignadas» cancels what's pending or accepted, and «Ajusta y vuelve a
  enviar» what was rejected (the old one is cancelled and the new one remembers it).
* **Only asesores with Captación** can have a route (G-002: route and GPS depend on Captación).
* A route: period (from / to), weekdays (Mon–Sat), 1 to 3 zonas with their hours and weekdays.
  Validation as G-083: dates, at least one day, zone days within the route days, end after start,
  no repeated zone, no overlapping hours the same day, and no other pending or accepted route of
  that asesor in those dates.
* The **asesor** gets «Nueva ruta asignada», accepts it or rejects it with a reason and an
  explanation (both required). The answer goes to Coordinación.
* **Mi ruta** (M04): today's zones of the accepted route plus what the agenda already has (citas,
  pedido deadlines); «Marcar llegada al siguiente punto» records the arrival at the next zone.
* The **Auxiliar** and **Gerencia** only consult; **Gerencia rates** accepted routes 1 to 5 (G-051):
  the average is the «Rutas del equipo» area of the Coordinador who created them.
* Every action is a `RutaEvento` (Registro de cambios).
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Ruta, RutaEvento, RutaLlegada, RutaZona, User
from app.models.enums import Cargo
from app.services import fechas
from app.services.errors import ConflictError, DomainError, NotFoundError, PermissionDeniedError
from app.services.pedidos import ZONAS
from app.services.policies import can_capture

ESTADOS = {
    "por_aceptar": ("Por aceptar", "warn"),
    "aceptada": ("✓ Aceptada", "ok"),
    "rechazada": ("✕ Rechazada", "bad"),
    "cancelada": ("Cancelada", "gray"),
}
# G-083: example reasons; the real list is PENDIENTE DE CONFIGURACIÓN
MOTIVOS = {
    "permiso": "Tengo permiso o incapacidad",
    "citas": "Tengo citas o compromisos en esas fechas",
    "zona": "No conozco la zona o queda muy lejos",
    "horario": "El horario no me sirve",
    "otro": "Otro motivo",
}
DIAS = {1: "Lun", 2: "Mar", 3: "Mié", 4: "Jue", 5: "Vie", 6: "Sáb"}
DIAS_CORTOS = {1: "L", 2: "M", 3: "X", 4: "J", 5: "V", 6: "S"}
MAX_ZONAS = 3
MAX_DIAS_RUTA = 92  # a route covers at most about a quarter
VIVAS = ("por_aceptar", "aceptada")


# ---------------------------------------------------------------- access


def puede_programar(u: User) -> bool:
    return u.is_active and u.cargo == Cargo.COORDINACION


def puede_consultar(u: User) -> bool:
    return u.is_active and u.cargo in (
        Cargo.COORDINACION,
        Cargo.GERENCIA,
        Cargo.AUXILIAR_ADMINISTRATIVA,
    )


def puede_usar(u: User) -> bool:
    return puede_consultar(u) or can_capture(u)


def ensure_uso(u: User) -> None:
    if not puede_usar(u):
        raise PermissionDeniedError(
            "Las rutas son para asesores con Captación. Si debes salir a captar, pide que te "
            "activen Captación."
        )


def ensure_programar(u: User) -> None:
    if not puede_programar(u):
        raise PermissionDeniedError("Las rutas las asigna Coordinación.")


def ensure_consultar(u: User) -> None:
    if not puede_consultar(u):
        raise PermissionDeniedError(
            "Las rutas del equipo las consultan Coordinación, Gerencia y la Auxiliar."
        )


# ---------------------------------------------------------------- formatting


def dia_semana(d: date) -> int:
    """1 = lunes … 7 = domingo."""
    return d.isoweekday()


def _fd(d: date) -> str:
    m = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    return f"{d.day} {m[d.month - 1]}"


def dias_txt(dias: list[int]) -> str:
    s = sorted(dias)
    if s == [1, 2, 3, 4, 5, 6]:
        return "L a S"
    if s == [1, 2, 3, 4, 5]:
        return "L a V"
    return "-".join(DIAS_CORTOS[d] for d in s)


def _h(t: time) -> str:
    return t.strftime("%H:%M")


def periodo_txt(r: Ruta) -> str:
    return _fd(r.desde) if r.desde == r.hasta else f"{_fd(r.desde)} al {_fd(r.hasta)}"


def zonas_txt(zonas: list[RutaZona] | list[dict[str, Any]]) -> str:
    out = []
    for z in zonas:
        if isinstance(z, RutaZona):
            out.append(f"{z.zona} ({dias_txt(z.dias)} {_h(z.hora_inicio)}–{_h(z.hora_fin)})")
        else:
            out.append(
                f"{z['zona']} ({dias_txt(z['dias'])} {_h(z['hora_inicio'])}–{_h(z['hora_fin'])})"
            )
    return " · ".join(out)


def resumen(r: Ruta) -> str:
    return f"{periodo_txt(r)} · {dias_txt(r.dias)} · {zonas_txt(r.zonas)}"


def _evento(
    db: Session, r: Ruta, actor: User | None, accion: str, antes=None, despues=None
) -> None:
    db.add(
        RutaEvento(
            ruta_id=r.id,
            accion=accion,
            antes=None if antes is None else str(antes)[:300],
            despues=None if despues is None else str(despues)[:500],
            actor_id=actor.id if actor else None,
        )
    )


# ---------------------------------------------------------------- validation


def _t(v: Any) -> time:
    if isinstance(v, time):
        return v
    try:
        h, m = str(v).strip().split(":")[:2]
        return time(int(h), int(m))
    except (ValueError, TypeError) as e:
        raise DomainError(f"Revisa la hora «{v}».") from e


def _dias(v: Any) -> list[int]:
    try:
        out = sorted({int(x) for x in (v or [])})
    except (TypeError, ValueError) as e:
        raise DomainError("Revisa los días de la semana.") from e
    if any(d not in DIAS for d in out):
        raise DomainError("Los días van de lunes a sábado.")
    return out


def normalizar(
    db: Session, data: dict[str, Any], *, excluir: uuid.UUID | None = None
) -> dict[str, Any]:
    """Check a route as G-083 says. Returns the clean data or raises DomainError/ConflictError."""
    asesor = db.get(User, data.get("asesor_id")) if data.get("asesor_id") else None
    if asesor is None or not asesor.is_active:
        raise DomainError("Elige el asesor.")
    if not can_capture(asesor):
        raise DomainError(
            f"{asesor.full_name} no tiene Captación activa: no puede tener ruta. "
            "Actívale Captación "
            "en «Actividades de empleados» si debe salir a captar."
        )
    d1, d2 = data.get("desde"), data.get("hasta")
    if not d1 or not d2 or d1 > d2:
        raise DomainError("Revisa las fechas: «Desde» debe ser anterior o igual a «Hasta».")
    if d2 < fechas.local_date(fechas.now()):
        raise DomainError("La ruta ya terminó: elige fechas desde hoy.")
    if (d2 - d1).days >= MAX_DIAS_RUTA:
        raise DomainError(f"Una ruta cubre máximo {MAX_DIAS_RUTA} días: divídela en varias.")
    dias = _dias(data.get("dias"))
    if not dias:
        raise DomainError("Elige al menos un día de la semana.")
    zs_in = data.get("zonas") or []
    if not 1 <= len(zs_in) <= MAX_ZONAS:
        raise DomainError("La ruta lleva de 1 a 3 zonas.")
    zonas = []
    for i, z in enumerate(zs_in, 1):
        nombre = (z.get("zona") or "").strip()
        if not nombre:
            raise DomainError(f"Falta la zona {i}.")
        if nombre not in ZONAS:
            raise DomainError(f"«{nombre}» no está en la lista de zonas.")
        h1, h2 = _t(z.get("hora_inicio")), _t(z.get("hora_fin"))
        zd = _dias(z.get("dias"))
        if not zd:
            raise DomainError(f"La zona {i} no tiene días.")
        if h2 <= h1:
            raise DomainError(f"En la zona {i} la hora final debe ser después de la inicial.")
        if any(d not in dias for d in zd):
            raise DomainError(f"La zona {i} tiene días que no están en los días de la ruta.")
        zonas.append({"zona": nombre, "hora_inicio": h1, "hora_fin": h2, "dias": zd})
    for i, a in enumerate(zonas):
        for b in zonas[i + 1 :]:
            if a["zona"] == b["zona"] and a["zona"] != "Otra zona":
                raise DomainError(f"Repetiste la zona {a['zona']}.")
            if (
                set(a["dias"]) & set(b["dias"])
                and a["hora_inicio"] < b["hora_fin"]
                and b["hora_inicio"] < a["hora_fin"]
            ):
                raise DomainError(
                    f"Las zonas {a['zona']} y {b['zona']} se cruzan en horario el mismo día."
                )
    q = select(Ruta).where(
        Ruta.asesor_id == asesor.id, Ruta.estado.in_(VIVAS), Ruta.desde <= d2, Ruta.hasta >= d1
    )
    if excluir:
        q = q.where(Ruta.id != excluir)
    if cruce := db.scalars(q.limit(1)).first():
        raise ConflictError(
            f"{asesor.full_name} ya tiene una ruta {ESTADOS[cruce.estado][0].lower().lstrip('✓ ')} "
            f"del {periodo_txt(cruce)}. Cancélala o elige otras fechas."
        )
    obs = (data.get("observacion") or "").strip()[:300] or None
    return {
        "asesor": asesor,
        "desde": d1,
        "hasta": d2,
        "dias": dias,
        "zonas": zonas,
        "observacion": obs,
    }


# ---------------------------------------------------------------- commands


def get(db: Session, user: User, id_: uuid.UUID) -> Ruta:
    ensure_uso(user)
    r = db.get(Ruta, id_)
    if r is None or (not puede_consultar(user) and r.asesor_id != user.id):
        raise NotFoundError("Esa ruta no existe.")
    return r


def crear(
    db: Session,
    data: dict[str, Any],
    *,
    actor: User,
    origen: str = "manual",
    reemplaza: Ruta | None = None,
) -> Ruta:
    ensure_programar(actor)
    if reemplaza is not None and reemplaza.estado != "rechazada":
        raise ConflictError("Solo se ajusta y vuelve a enviar una ruta rechazada.")
    n = normalizar(db, data)
    r = Ruta(
        asesor_id=n["asesor"].id,
        desde=n["desde"],
        hasta=n["hasta"],
        dias=n["dias"],
        observacion=n["observacion"],
        origen=origen,
        creado_por_id=actor.id,
        reemplaza_id=reemplaza.id if reemplaza else None,
    )
    for i, z in enumerate(n["zonas"]):
        r.zonas.append(RutaZona(orden=i, **z))
    db.add(r)
    db.flush()
    if reemplaza is not None:
        reemplaza.estado, reemplaza.cancelada_at = "cancelada", fechas.now()
        _evento(
            db,
            reemplaza,
            actor,
            "Ajustó y volvió a enviar la ruta",
            "Rechazada",
            "Cancelada · reemplazada",
        )
    _evento(
        db,
        r,
        actor,
        "Asignó la ruta" + (" (plantilla de Excel)" if origen == "excel" else ""),
        None,
        f"{n['asesor'].full_name} · {resumen(r)} · Por aceptar",
    )
    db.flush()
    return r


def cancelar(db: Session, r: Ruta, *, actor: User) -> Ruta:
    ensure_programar(actor)
    if r.estado not in VIVAS:
        raise ConflictError("Solo se cancela una ruta por aceptar o aceptada.")
    if r.hasta < fechas.local_date(fechas.now()):
        raise ConflictError("Esa ruta ya terminó.")
    antes = ESTADOS[r.estado][0]
    r.estado, r.cancelada_at = "cancelada", fechas.now()
    _evento(db, r, actor, "Canceló la ruta", antes, "Cancelada")
    db.flush()
    return r


def responder(
    db: Session, r: Ruta, acepta: bool, motivo: str | None, texto: str | None, *, actor: User
) -> Ruta:
    """The asesor accepts or rejects (G-083: reason and explanation, both required)."""
    if r.asesor_id != actor.id:
        raise PermissionDeniedError("Solo el asesor de la ruta la acepta o la rechaza.")
    if r.estado != "por_aceptar":
        raise ConflictError("Esa ruta ya no está por aceptar.")
    if not acepta:
        texto = (texto or "").strip()
        if motivo not in MOTIVOS or len(texto) < 5:
            raise DomainError("Elige el motivo y explícalo para rechazar la ruta.")
        r.motivo, r.motivo_texto = motivo, texto[:500]
    r.estado = "aceptada" if acepta else "rechazada"
    r.respondida_at = fechas.now()
    _evento(
        db,
        r,
        actor,
        "Aceptó la ruta" if acepta else "Rechazó la ruta",
        "Por aceptar",
        "Aceptada" if acepta else f"Rechazada · {MOTIVOS[motivo]} · «{texto[:300]}»",
    )
    db.flush()
    return r


def calificar(db: Session, r: Ruta, puntos: int, *, actor: User) -> Ruta:
    """G-051: Gerencia rates 1 to 5 the routes Coordinación created."""
    if not (actor.is_active and actor.cargo == Cargo.GERENCIA):
        raise PermissionDeniedError("Las rutas las califica Gerencia.")
    if r.estado != "aceptada":
        raise ConflictError("Se califican las rutas aceptadas.")
    if not 1 <= puntos <= 5:
        raise DomainError("La calificación va de 1 a 5.")
    antes = f"{r.calificacion} de 5" if r.calificacion else None
    r.calificacion, r.calificada_at, r.calificada_por_id = puntos, fechas.now(), actor.id
    _evento(db, r, actor, "Calificó la ruta", antes, f"{puntos} de 5")
    db.flush()
    return r


# ---------------------------------------------------------------- views


def fila(r: Ruta, viewer: User) -> dict[str, Any]:
    e, cls = ESTADOS[r.estado]
    prog = puede_programar(viewer)
    hoy = fechas.local_date(fechas.now())
    return {
        "id": r.id,
        "asesor_id": r.asesor_id,
        "asesor": r.asesor.full_name,
        "desde": r.desde,
        "hasta": r.hasta,
        "dias": r.dias,
        "zonas": [
            {
                "id": z.id,
                "zona": z.zona,
                "hora_inicio": _h(z.hora_inicio),
                "hora_fin": _h(z.hora_fin),
                "dias": z.dias,
            }
            for z in r.zonas
        ],
        "periodo_txt": periodo_txt(r),
        "dias_txt": dias_txt(r.dias),
        "zonas_txt": zonas_txt(r.zonas),
        "observacion": r.observacion,
        "origen": r.origen,
        "estado": r.estado,
        "estado_txt": e,
        "estado_cls": cls,
        "motivo_txt": f"{MOTIVOS.get(r.motivo or '', r.motivo)} · «{r.motivo_texto}»"
        if r.motivo
        else None,
        "asignada": f"Asignada {fechas.fmt(r.created_at)} · "
        + ("desde plantilla de Excel" if r.origen == "excel" else "manual")
        + (f" · por {r.creado_por.full_name}" if r.creado_por else "")
        + (f" · respondió {fechas.fmt(r.respondida_at)}" if r.respondida_at else ""),
        "calificacion": r.calificacion,
        "puede_cancelar": prog and r.estado in VIVAS and r.hasta >= hoy,
        "puede_reenviar": prog and r.estado == "rechazada",
        "puede_calificar": viewer.cargo == Cargo.GERENCIA and r.estado == "aceptada",
        "puede_responder": viewer.id == r.asesor_id and r.estado == "por_aceptar",
    }


def listar(
    db: Session,
    viewer: User,
    *,
    desde: date | None,
    hasta: date | None,
    asesor_id: uuid.UUID | None,
    estado: str | None,
) -> list[Ruta]:
    ensure_consultar(viewer)
    q = select(Ruta)
    if desde:
        q = q.where(Ruta.hasta >= desde)
    if hasta:
        q = q.where(Ruta.desde <= hasta)
    if asesor_id:
        q = q.where(Ruta.asesor_id == asesor_id)
    if estado:
        q = q.where(Ruta.estado == estado)
    return list(db.scalars(q.order_by(Ruta.created_at.desc())).unique())


def asesores(db: Session) -> list[User]:
    us = db.scalars(select(User).where(User.is_active).order_by(User.full_name)).unique()
    return [u for u in us if can_capture(u)]


def vigentes(db: Session, user: User, d: date) -> list[Ruta]:
    return list(
        db.scalars(
            select(Ruta).where(
                Ruta.asesor_id == user.id,
                Ruta.estado == "aceptada",
                Ruta.desde <= d,
                Ruta.hasta >= d,
            )
        ).unique()
    )


def zonas_del_dia(db: Session, user: User, d: date) -> list[RutaZona]:
    dia = dia_semana(d)
    out = [z for r in vigentes(db, user, d) if dia in r.dias for z in r.zonas if dia in z.dias]
    return sorted(out, key=lambda z: z.hora_inicio)


def llegadas(db: Session, zonas: list[RutaZona], d: date) -> dict[uuid.UUID, RutaLlegada]:
    if not zonas:
        return {}
    return {
        x.zona_id: x
        for x in db.scalars(
            select(RutaLlegada).where(
                RutaLlegada.zona_id.in_([z.id for z in zonas]), RutaLlegada.fecha == d
            )
        )
    }


def mi_ruta(db: Session, user: User) -> dict[str, Any]:
    """M04: today's timeline (route zones, citas, pedido deadlines) and the routes to answer."""
    if not can_capture(user):
        raise PermissionDeniedError(
            "«Mi ruta» es para asesores con Captación: marcas en una sede. "
            "Si debes salir a captar, "
            "pide que te activen Captación."
        )
    from app.services import agenda

    hoy = fechas.local_date(fechas.now())
    now = fechas.now()
    zs = zonas_del_dia(db, user, hoy)
    ll = llegadas(db, zs, hoy)
    tl: list[dict[str, Any]] = []
    siguiente = next((z for z in zs if z.id not in ll), None)
    for z in zs:
        x = ll.get(z.id)
        fin = datetime.combine(hoy, z.hora_fin, tzinfo=fechas.BOGOTA)
        if x:
            e, cls = "✓ Hecho", "ok"
        elif now > fin:
            e, cls = "Sin llegada", "bad"
        else:
            e, cls = "Pendiente", "gray"
        tl.append(
            {
                "id": f"zona:{z.id}",
                "tipo": "ruta",
                "hora": _h(z.hora_inicio),
                "titulo": f"Captación · {z.zona}",
                "sub": f"Ruta del coordinador · hasta {_h(z.hora_fin)}"
                + (
                    f" · llegada {x.llegada_at.astimezone(fechas.BOGOTA).strftime('%H:%M')}"
                    if x
                    else ""
                )
                + (f" · «{z.ruta.observacion}»" if z.ruta.observacion else ""),
                "estado_txt": e,
                "estado_cls": cls,
                "link": None,
            }
        )
    for it in agenda.sistema(db, user, user, hoy, hoy):
        if it["tipo"] == "ruta":  # already above, with the arrival
            continue
        tl.append(
            {
                "id": it["id"],
                "tipo": "mia" if it["tipo"] == "ped" else "cita",
                "hora": it["hora"].strftime("%H:%M") if it.get("hora") else "",
                "titulo": it["titulo"],
                "sub": it["sub"],
                "estado_txt": it["estado_txt"],
                "estado_cls": it["estado_cls"],
                "link": it["link"],
            }
        )
    tl.sort(key=lambda t: t["hora"] or "99")
    hechos = sum(1 for t in tl if t["estado_txt"].startswith("✓"))
    mias = list(
        db.scalars(
            select(Ruta)
            .where(Ruta.asesor_id == user.id, Ruta.estado.in_(VIVAS), Ruta.hasta >= hoy)
            .order_by(Ruta.desde)
        ).unique()
    )
    return {
        "fecha": hoy,
        "timeline": tl,
        "hechos": hechos,
        "total": len(tl),
        "siguiente": {"id": siguiente.id, "zona": siguiente.zona, "hora": _h(siguiente.hora_inicio)}
        if siguiente
        else None,
        "por_aceptar": [fila(r, user) for r in mias if r.estado == "por_aceptar"],
        "aceptadas": [fila(r, user) for r in mias if r.estado == "aceptada"],
        "motivos": MOTIVOS,
    }


def llegar(db: Session, user: User, zona_id: uuid.UUID, nota: str | None = None) -> RutaLlegada:
    """«Marcar llegada al siguiente punto»: a zone of today's accepted route, once per day."""
    hoy = fechas.local_date(fechas.now())
    z = db.get(RutaZona, zona_id)
    if z is None or z.ruta.asesor_id != user.id:
        raise NotFoundError("Esa zona no está en tu ruta.")
    if z not in zonas_del_dia(db, user, hoy):
        raise DomainError("Esa zona no está en tu ruta de hoy.")
    if db.scalar(
        select(RutaLlegada.id).where(RutaLlegada.zona_id == z.id, RutaLlegada.fecha == hoy)
    ):
        raise ConflictError(f"Ya marcaste la llegada a {z.zona} hoy.")
    x = RutaLlegada(
        zona_id=z.id, fecha=hoy, llegada_at=fechas.now(), nota=(nota or "").strip()[:300] or None
    )
    db.add(x)
    _evento(db, z.ruta, user, "Marcó llegada", None, f"{z.zona} · {fechas.fmt(x.llegada_at)}")
    db.flush()
    return x


def ubicaciones(db: Session, viewer: User) -> list[dict[str, Any]]:
    """X08 «Ubicación y ruta de cada persona» · where each person checks in today."""
    ensure_consultar(viewer)
    hoy = fechas.local_date(fechas.now())
    out = []
    for u in db.scalars(
        select(User).where(User.is_active).order_by(User.cargo, User.full_name)
    ).unique():
        zs = zonas_del_dia(db, u, hoy) if can_capture(u) else []
        rutas_vig = vigentes(db, u, hoy) if can_capture(u) else []
        if zs:
            donde, cls = "En ruta · " + " · ".join(dict.fromkeys(z.zona for z in zs)), "warn"
        elif rutas_vig:
            donde, cls = "Oficina · Sede principal (hoy no tiene zona)", "ok"
        elif u.cargo == Cargo.ASESOR and u.funcion is None:
            donde, cls = "Oficina · Sede principal", "ok"
        else:
            donde, cls = "Sede principal", "ok"
        if can_capture(u):
            nota = None
        elif u.cargo == Cargo.ASESOR and u.funcion is None:
            nota = "Sin Captación: no tiene ruta ni GPS"
        elif u.cargo == Cargo.COORDINACION:
            nota = "Coordinación queda en la sede principal"
        else:
            nota = "Este cargo no tiene ruta"
        out.append(
            {
                "id": u.id,
                "nombre": u.full_name,
                "cargo": u.cargo.value,
                "donde": donde,
                "cls": cls,
                "nota": nota,
            }
        )
    return out


# ---------------------------------------------------------------- Excel template (CSV)

PLANTILLA_COLS = [
    "asesor_correo",
    "desde",
    "hasta",
    "dias",
    "zona_1",
    "horario_1",
    "dias_1",
    "zona_2",
    "horario_2",
    "dias_2",
    "zona_3",
    "horario_3",
    "dias_3",
    "observacion",
]
_LETRA = {"L": 1, "M": 2, "X": 3, "J": 4, "V": 5, "S": 6}


def plantilla() -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(PLANTILLA_COLS)
    w.writerow(
        [
            "asesor@example.com",
            "2026-11-09",
            "2026-11-13",
            "L a V",
            "Laureles",
            "08:00-12:00",
            "L a V",
            "Belén",
            "14:00-17:00",
            "L-X-V",
            "",
            "",
            "",
            "Captación de apartamentos en oferta",
        ]
    )
    return "﻿" + buf.getvalue()


def _dias_txt_a_lista(v: str) -> list[int]:
    v = (v or "").strip().upper().replace(" ", "")
    if v in ("LAV", "L-V"):
        return [1, 2, 3, 4, 5]
    if v in ("LAS", "L-S"):
        return [1, 2, 3, 4, 5, 6]
    out = []
    for p in v.replace(",", "-").split("-"):
        if p not in _LETRA:
            raise DomainError(f"Días «{v}» no válidos: usa L, M, X, J, V, S (ej.: L-X-V o L a V).")
        out.append(_LETRA[p])
    return out


def _fecha(v: str) -> date:
    v = (v or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    raise DomainError(f"Fecha «{v}» no válida (usa AAAA-MM-DD o DD/MM/AAAA).")


def importar(db: Session, texto: str, confirmar: bool, *, actor: User) -> dict[str, Any]:
    """G-083 «Subir plantilla»: check row by row; with confirmar, assign the correct ones."""
    ensure_programar(actor)
    texto = (texto or "").lstrip("﻿")
    if not texto.strip():
        raise DomainError("El archivo está vacío.")
    muestra = texto.splitlines()[0]
    lector = csv.DictReader(
        io.StringIO(texto), delimiter=";" if muestra.count(";") >= muestra.count(",") else ","
    )
    if not lector.fieldnames or "asesor_correo" not in [c.strip() for c in lector.fieldnames]:
        raise DomainError(
            "El archivo no tiene las columnas de la plantilla: descárgala y vuelve a llenarla."
        )
    filas, ok_datos = [], []
    vistos: list[dict[str, Any]] = []
    for n, row in enumerate(lector, 2):
        row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        if not any(row.values()):
            continue
        correo = row.get("asesor_correo", "").lower()
        asesor = db.scalar(select(User).where(User.email == correo)) if correo else None
        nombre = asesor.full_name if asesor else (correo or "(sin asesor)")
        error, data = None, None
        try:
            if asesor is None:
                raise DomainError(f"No hay un usuario con el correo «{correo}».")
            zonas = []
            for i in (1, 2, 3):
                z, h, dz = (
                    row.get(f"zona_{i}", ""),
                    row.get(f"horario_{i}", ""),
                    row.get(f"dias_{i}", ""),
                )
                if not (z or h or dz):
                    if i == 1:
                        raise DomainError("Falta la zona 1.")
                    continue
                if "-" not in h:
                    raise DomainError(f"Horario de la zona {i} no válido (ej.: 08:00-12:00).")
                h1, h2 = h.split("-", 1)
                zonas.append(
                    {
                        "zona": z,
                        "hora_inicio": h1,
                        "hora_fin": h2,
                        "dias": _dias_txt_a_lista(dz or row.get("dias", "")),
                    }
                )
            data = {
                "asesor_id": asesor.id,
                "desde": _fecha(row.get("desde", "")),
                "hasta": _fecha(row.get("hasta", "")),
                "dias": _dias_txt_a_lista(row.get("dias", "")),
                "zonas": zonas,
                "observacion": row.get("observacion"),
            }
            limpio = normalizar(db, data)
            for v in vistos:  # rows of the same file can't overlap either
                if (
                    v["asesor"].id == asesor.id
                    and v["desde"] <= limpio["hasta"]
                    and limpio["desde"] <= v["hasta"]
                ):
                    raise ConflictError(
                        "Otra fila del archivo ya le asigna ruta a "
                        f"{asesor.full_name} en esas fechas."
                    )
            vistos.append(limpio)
        except (DomainError, ConflictError) as e:
            error = str(e.args[0] if e.args else e)
        filas.append(
            {
                "fila": n,
                "asesor": nombre,
                "periodo": f"{row.get('desde', '')} al {row.get('hasta', '')} · "
                f"{row.get('dias', '')}",
                "zonas": " · ".join(
                    f"{row.get(f'zona_{i}') or '(sin zona)'} {row.get(f'horario_{i}', '')}"
                    for i in (1, 2, 3)
                    if row.get(f"zona_{i}") or row.get(f"horario_{i}")
                ),
                "error": error,
            }
        )
        if error is None:
            ok_datos.append(data)
    if not filas:
        raise DomainError("El archivo no tiene filas con rutas.")
    asignadas = 0
    if confirmar:
        for d in ok_datos:
            crear(db, d, actor=actor, origen="excel")
            asignadas += 1
    return {"filas": filas, "correctas": len(ok_datos), "total": len(filas), "asignadas": asignadas}


# ---------------------------------------------------------------- for other modules


def agenda_items(
    db: Session, target: User, d1: date, d2: date, *, propia: bool
) -> list[dict[str, Any]]:
    """Route zones in the agenda (G-030: «ruta asignada»), read-only."""
    if not can_capture(target):
        return []
    rs = db.scalars(
        select(Ruta).where(
            Ruta.asesor_id == target.id,
            Ruta.estado == "aceptada",
            Ruta.desde <= d2,
            Ruta.hasta >= d1,
        )
    ).unique()
    out = []
    for r in rs:
        d = max(d1, r.desde)
        while d <= min(d2, r.hasta):
            dia = dia_semana(d)
            if dia in r.dias:
                for z in r.zonas:
                    if dia in z.dias:
                        out.append(
                            {
                                "id": f"ruta:{z.id}:{d.isoformat()}",
                                "k": "sys",
                                "tipo": "ruta",
                                "fecha": d,
                                "hora": z.hora_inicio,
                                "titulo": f"Ruta · {z.zona}",
                                "sub": f"{_h(z.hora_inicio)}–{_h(z.hora_fin)}"
                                + (f" · {r.observacion}" if r.observacion else ""),
                                "estado_txt": "Ruta",
                                "estado_cls": "info",
                                "link": "/rutas" if propia else None,
                            }
                        )
            d += timedelta(days=1)
    return out


def cumplimiento_coordinador(
    db: Session, coord: User, d1: date, d2: date
) -> tuple[float, int] | None:
    """G-051: average rating (1–5) of the accepted routes the Coordinador created that overlap the
    period. None when nothing is rated."""
    rs = db.scalars(
        select(Ruta).where(
            Ruta.creado_por_id == coord.id,
            Ruta.calificacion.is_not(None),
            Ruta.desde <= d2,
            Ruta.hasta >= d1,
            or_(Ruta.estado == "aceptada", Ruta.estado == "cancelada"),
        )
    ).unique()
    notas = [r.calificacion for r in rs if r.calificacion]
    if not notas:
        return None
    return sum(notas) / len(notas), len(notas)
