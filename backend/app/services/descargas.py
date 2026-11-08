"""Descargas del personal (prototype X10).

* **What**: one CSV (opens in Excel, `;` separated with a BOM, like every other export in the app)
  per tab, built from the data the modules already keep:
  - **Preoperacionales**: one row per person and business day that counts, «Realizado» or «No
    realizado», with the answers, novedad, review and the month's score (same rules as
    «Mi preoperacional»: from the person's start, business days, not when it's switched off).
  - **Asistencia**: one row per person and day with a marcación (entrada, salida, impuntualidad,
    discounted minutes, accepted overtime), as K17's «Descargar Excel».
  - **Ausencias y permisos**: one row per absence that touches the range, including the cancelled
    ones (with who and why).
  - **Capacitaciones**: one row per person and training (programmed or registered by the person),
    with the answer, whether they attended and the reason, what they learned. Coordinación
    programs trainings but doesn't download this file (G-047).
  - **Pausas activas**: one row per person, working day and pause that already closed: scheduled
    time, «Realizada» (and when), «No realizada» or «Ausencia», and the person's compliance.
  «PDF (con resumen)» is pending.
* **Filters** (X10): everyone, one cargo group (Asesores, Atención y Preventa, Coordinación,
  Administrativa, Gerencia) or one person, between two dates (at most a year).
* **Who**: the Auxiliar administrativa (X10 is hers) and Gerencia download everyone. Coordinación
  downloads its team, with each module's rule: preoperacionales of asesores, Atención y la Auxiliar;
  asistencia of asesores and Atención; ausencias of everyone but Gerencia. Everyone else gets 403.
* Every download is logged in `configuracion_eventos` (section «descargas») and shows in «Registro
  de cambios» (module «Descargas») and in «Descargas recientes».
"""

from __future__ import annotations

import csv
import io
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConfigEvento, Marcacion, Novedad, User
from app.models.enums import Cargo, EstadoNovedad
from app.services import asistencia, fechas, preoperacional
from app.services import novedades as nov
from app.services.errors import DomainError, NotFoundError, PermissionDeniedError

SECCION = "descargas"
MAX_DIAS = 366
GRUPOS = {
    "ase": "Asesores",
    "ate": "Atención y Preventa",
    "coo": "Coordinación",
    "aux": "Administrativa",
    "ger": "Gerencia",
}
TODOS = frozenset(GRUPOS)


def grupo(u: User) -> str:
    if u.cargo == Cargo.GERENCIA:
        return "ger"
    if u.cargo == Cargo.COORDINACION:
        return "coo"
    if u.cargo == Cargo.AUXILIAR_ADMINISTRATIVA:
        return "aux"
    if u.cargo == Cargo.ATENCION_CLIENTE or u.funcion is not None:
        return "ate"
    return "ase"


@dataclass(frozen=True)
class Tipo:
    key: str
    titulo: str
    archivo: str
    contenido: str
    disponible: bool
    # groups each manager can download (None: same as Gerencia)
    coord: frozenset[str] = frozenset()
    todos: frozenset[str] = TODOS


TIPOS: dict[str, Tipo] = {
    t.key: t
    for t in (
        Tipo(
            "pre",
            "Preoperacionales",
            "Preoperacional",
            "Una fila por persona y día hábil: fecha y hora, medio de transporte y placa, "
            "respuestas SÍ/NO, novedades y observaciones, realizado o no realizado, si la novedad "
            "fue revisada y el puntaje del mes.",
            True,
            coord=frozenset({"ase", "ate", "aux"}),
        ),
        Tipo(
            "asi",
            "Asistencia",
            "Asistencia",
            "Una fila por persona y día con marcación: ubicación asignada y dónde marcó, entrada "
            "y estado (a tiempo, impuntual leve o grave), salida y estado, minutos que se "
            "descuentan, horas extra aceptadas y observación.",
            True,
            coord=frozenset({"ase", "ate"}),
        ),
        Tipo(
            "aus",
            "Ausencias y permisos",
            "Ausencias",
            "Una fila por ausencia que toca el periodo: tipo (incapacidad, permiso remunerado o no "
            "remunerado), desde, hasta, días dentro del periodo, observación, soportes, quién la "
            "registró y si fue anulada (con el motivo).",
            True,
            coord=frozenset({"ase", "ate", "aux", "coo"}),
            todos=TODOS - {"ger"},
        ),
        Tipo(
            "pau",
            "Pausas activas",
            "Pausas_activas",
            "Una fila por persona, día hábil y pausa (mañana o tarde): hora programada, hora en "
            "que marcó «Realizada», o «No realizada» o «Ausencia», y el cumplimiento del periodo "
            "de la persona.",
            True,
            coord=frozenset({"ase", "ate"}),
        ),
        Tipo(
            "cap",
            "Capacitaciones",
            "Capacitaciones",
            "Una fila por persona y capacitación: fecha y hora, tema, área, quién la presentó, "
            "lugar, origen (programada o registrada por la persona), estado, respuesta, si "
            "participó o no y el motivo, qué aprendió y observaciones.",
            True,
            # G-047: Coordinación programs trainings but doesn't download the Excel
            coord=frozenset(),
            todos=TODOS - {"ger"},
        ),
    )
}


# ---------------------------------------------------------------- access


def puede(user: User) -> bool:
    return user.is_active and user.cargo in (
        Cargo.AUXILIAR_ADMINISTRATIVA,
        Cargo.GERENCIA,
        Cargo.COORDINACION,
    )


def ensure(user: User) -> None:
    if not puede(user):
        raise PermissionDeniedError(
            "Las descargas del personal las hacen la Auxiliar administrativa, Gerencia y "
            "Coordinación."
        )


def grupos_de(user: User, t: Tipo) -> frozenset[str]:
    return t.coord if user.cargo == Cargo.COORDINACION else t.todos


def _tipo(key: str) -> Tipo:
    t = TIPOS.get(key)
    if t is None:
        raise NotFoundError("Esa descarga no existe.")
    if not t.disponible:
        raise DomainError(
            f"«{t.titulo}» todavía no existe en el software: no hay datos para descargar."
        )
    return t


# ---------------------------------------------------------------- filters


@dataclass
class Filtros:
    tipo: str
    desde: date
    hasta: date
    alcance: str = "tod"  # tod · car · emp
    grupo: str | None = None
    user_id: uuid.UUID | None = None


def _personas(db: Session, user: User, t: Tipo, f: Filtros) -> tuple[list[User], str]:
    """The people in the file and the «who» text («Todos», «Asesores», a name)."""
    permitidos = grupos_de(user, t)
    if not permitidos:
        raise PermissionDeniedError(
            f"La descarga de {t.titulo.lower()} es de la Auxiliar administrativa y Gerencia."
        )
    gente = [
        u
        for u in db.scalars(select(User).order_by(User.full_name)).unique()
        if grupo(u) in permitidos and (u.id != user.id or user.cargo != Cargo.COORDINACION)
    ]
    if f.alcance == "car":
        if f.grupo not in GRUPOS:
            raise DomainError("Elige el cargo.")
        if f.grupo not in permitidos:
            raise PermissionDeniedError(f"No descargas {t.titulo.lower()} de {GRUPOS[f.grupo]}.")
        return [u for u in gente if grupo(u) == f.grupo], GRUPOS[f.grupo]
    if f.alcance == "emp":
        if f.user_id is None:
            raise DomainError("Elige el empleado.")
        u = next((u for u in gente if u.id == f.user_id), None)
        if u is None:
            raise PermissionDeniedError(f"No descargas {t.titulo.lower()} de esa persona.")
        return [u], u.full_name
    if f.alcance != "tod":
        raise DomainError("Elige si es de todo el personal, de un cargo o de un empleado.")
    return gente, "Todos"


def _validar(f: Filtros) -> None:
    if f.desde > f.hasta:
        raise DomainError("Revisa las fechas: «Desde» debe ser anterior o igual a «Hasta».")
    if (f.hasta - f.desde).days + 1 > MAX_DIAS:
        raise DomainError("El periodo puede ser de hasta un año.")


# ---------------------------------------------------------------- builders


Fila = list[Any]


def _meses(d1: date, d2: date) -> list[tuple[date, date]]:
    out, m = [], d1.replace(day=1)
    while m <= d2:
        nxt = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
        out.append((m, nxt - timedelta(days=1)))
        m = nxt
    return out


def _hm(dt) -> str:
    return dt.astimezone(fechas.BOGOTA).strftime("%Y-%m-%d %H:%M") if dt else ""


def _pre(db: Session, gente: list[User], d1: date, d2: date) -> tuple[Fila, list[Fila]]:
    head = [
        "Persona",
        "Cargo",
        "Fecha",
        "Estado",
        "Hora",
        "Medio",
        "Placa",
        "Respuestas",
        "Respuestas NO",
        "Novedad",
        "Observaciones",
        "Novedad revisada por",
        "Revisada",
        "Puntaje del mes",
        "% del mes",
    ]
    rows: list[Fila] = []
    activo = preoperacional.config(db)
    for first, last in _meses(d1, d2):
        regs = preoperacional._registros(db, [u.id for u in gente], first, last)
        for u in gente:
            r = regs.get(u.id, {})
            res, faltan = preoperacional.resumen_mes(u, r, first, last, activo[u.cargo])
            pts = "" if res.puntaje is None else res.puntaje
            pct = "" if res.pct is None else res.pct
            dias = sorted({d for d in r if d1 <= d <= d2} | {d for d in faltan if d1 <= d <= d2})
            for d in dias:
                p = r.get(d)
                cargo = GRUPOS[grupo(u)]
                if p is None:
                    vacio = [""] * 9
                    fecha = d.isoformat()
                    rows.append([u.full_name, cargo, fecha, "No realizado", *vacio, pts, pct])
                    continue
                resp = p.respuestas or []
                rows.append(
                    [
                        u.full_name,
                        cargo,
                        d.isoformat(),
                        "Realizado",
                        p.realizado_at.astimezone(fechas.BOGOTA).strftime("%H:%M"),
                        preoperacional.MEDIO_LABELS[p.medio],
                        p.placa or "",
                        " · ".join(
                            f"{i} {'SÍ' if r.get('si') else 'NO'}" for i, r in enumerate(resp, 1)
                        )
                        or "Solo reporte del trayecto",
                        " · ".join(str(r.get("pregunta", "")) for r in resp if not r.get("si")),
                        "Sí" if p.tiene_novedad else "No",
                        p.observaciones or "",
                        p.revisado_por_name or "",
                        _hm(p.revisado_at),
                        pts,
                        pct,
                    ]
                )
    rows.sort(key=lambda x: (x[0], x[2]))
    return head, rows


def _asi(db: Session, gente: list[User], d1: date, d2: date) -> tuple[Fila, list[Fila]]:
    head = [
        "Persona",
        "Cargo",
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
    ids = [u.id for u in gente]
    rows: list[Fila] = []
    if ids:
        for m in db.scalars(
            select(Marcacion)
            .where(Marcacion.user_id.in_(ids), Marcacion.fecha >= d1, Marcacion.fecha <= d2)
            .order_by(Marcacion.fecha)
        ).unique():
            r = asistencia.fila(db, m)
            rows.append(
                [
                    m.user.full_name,
                    GRUPOS[grupo(m.user)],
                    m.fecha.isoformat(),
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
    rows.sort(key=lambda x: (x[0], x[2]))
    return head, rows


def _aus(db: Session, gente: list[User], d1: date, d2: date) -> tuple[Fila, list[Fila]]:
    head = [
        "Número",
        "Persona",
        "Cargo",
        "Tipo",
        "Desde",
        "Hasta",
        "Días en el periodo",
        "Observación",
        "Soportes",
        "Registrada por",
        "Registrada",
        "Estado",
        "Anulada por",
        "Motivo de anulación",
    ]
    ids = [u.id for u in gente]
    rows: list[Fila] = []
    if ids:
        for n in db.scalars(
            select(Novedad)
            .where(Novedad.empleado_id.in_(ids), Novedad.desde <= d2, Novedad.hasta >= d1)
            .order_by(Novedad.desde)
        ).unique():
            rows.append(
                [
                    f"NOV-{n.numero:04d}",
                    n.empleado.full_name,
                    GRUPOS[grupo(n.empleado)],
                    nov.TIPO_LABELS[n.tipo],
                    n.desde.isoformat(),
                    n.hasta.isoformat(),
                    nov.dias_en(n, d1, d2),
                    n.observacion or "",
                    n.soportes,
                    n.registrada_por.full_name if n.registrada_por else "",
                    _hm(n.created_at),
                    nov.ESTADO_LABELS[n.estado],
                    n.anulada_por.full_name if n.anulada_por else "",
                    n.motivo_anulacion or "" if n.estado == EstadoNovedad.ANULADA else "",
                ]
            )
    rows.sort(key=lambda x: (x[1], x[4]))
    return head, rows


def _cap(db: Session, gente: list[User], d1: date, d2: date) -> tuple[Fila, list[Fila]]:
    from app.models import Capacitacion, CapacitacionParticipante
    from app.services import capacitaciones as cap

    head = [
        "Código",
        "Fecha",
        "Hora",
        "Tema",
        "Área",
        "Presentó",
        "Lugar o enlace",
        "Origen",
        "Estado de la capacitación",
        "Persona",
        "Cargo",
        "Respuesta",
        "Participó",
        "Motivo",
        "Qué aprendió",
        "Observaciones",
    ]
    ids = [u.id for u in gente]
    rows: list[Fila] = []
    if not ids:
        return head, rows
    q = (
        select(CapacitacionParticipante)
        .join(Capacitacion, Capacitacion.id == CapacitacionParticipante.capacitacion_id)
        .where(
            CapacitacionParticipante.user_id.in_(ids),
            Capacitacion.inicio_at >= fechas.start_of_day(d1),
            Capacitacion.inicio_at < fechas.start_of_day(d2 + timedelta(days=1)),
        )
    )
    resp = {"pendiente": "Por responder", "acepta": "Aceptó", "no": "No participa"}
    estado = {"programada": "Programada", "realizada": "Realizada", "cancelada": "Cancelada"}
    for p in db.scalars(q).unique():
        c = p.capacitacion
        local = c.inicio_at.astimezone(fechas.BOGOTA)
        participo = "" if p.asistio is None else ("Sí" if p.asistio else "No")
        motivo = (p.motivo or "") + (f" · {p.motivo_detalle}" if p.motivo_detalle else "")
        rows.append(
            [
                c.code,
                local.date().isoformat(),
                local.strftime("%H:%M"),
                c.tema,
                c.area,
                c.presenta,
                c.lugar or "",
                cap.origen_txt(c),
                estado.get(c.estado, c.estado),
                p.user.full_name,
                GRUPOS[grupo(p.user)],
                resp.get(p.respuesta, p.respuesta),
                participo,
                motivo,
                p.aprendio or "",
                p.observaciones or "",
            ]
        )
    rows.sort(key=lambda x: (x[1], x[2], x[0], x[9]))
    return head, rows


def _pau(db: Session, gente: list[User], d1: date, d2: date) -> tuple[Fila, list[Fila]]:
    from app.services import pausas

    head = [
        "Persona",
        "Cargo",
        "Fecha",
        "Pausa",
        "Hora programada",
        "Estado",
        "Hora en que marcó «Realizada»",
        "Cumplimiento del periodo (%)",
    ]
    now = fechas.now()
    hoy = fechas.local_date(now)
    if d1 > hoy:
        return head, []
    ss = pausas.slots(db, gente, d1, min(d2, hoy), now)
    pct = {}
    for u in gente:
        p, _h, _f = pausas.cumplimiento([s for s in ss if s.user.id == u.id])
        pct[u.id] = "" if p is None else p
    rows: list[Fila] = []
    for s in ss:
        if s.estado in ("programada", "en_curso"):
            continue  # not closed yet
        e, _cls = s.txt
        rows.append(
            [
                s.user.full_name,
                GRUPOS[grupo(s.user)],
                s.fecha.isoformat(),
                pausas.TURNOS[s.turno].capitalize(),
                s.programada.strftime("%H:%M"),
                e.split(" · ")[0].replace("✓ ", ""),
                s.realizada_at.astimezone(fechas.BOGOTA).strftime("%H:%M")
                if s.realizada_at
                else "",
                pct[s.user.id],
            ]
        )
    rows.sort(key=lambda x: (x[0], x[2], x[3] != "Mañana"))
    return head, rows


BUILDERS: dict[str, Callable[[Session, list[User], date, date], tuple[Fila, list[Fila]]]] = {
    "pre": _pre,
    "asi": _asi,
    "aus": _aus,
    "cap": _cap,
    "pau": _pau,
}


# ---------------------------------------------------------------- API


def _fd(d: date) -> str:
    return f"{d.day} {fechas._MESES[d.month - 1]} {d.year}"


def _archivo(t: Tipo, quien: str, f: Filtros) -> str:
    # ASCII only: the name goes in an HTTP header («Atención» → «Atencion»)
    plano = unicodedata.normalize("NFKD", quien.title()).encode("ascii", "ignore").decode()
    q = "".join(ch for ch in plano if ch.isalnum()) or "Todos"
    return f"CDC_{t.archivo}_{q}_{f.desde.isoformat()}_a_{f.hasta.isoformat()}.csv"


def _construir(db: Session, user: User, f: Filtros):
    ensure(user)
    t = _tipo(f.tipo)
    _validar(f)
    gente, quien = _personas(db, user, t, f)
    head, rows = BUILDERS[t.key](db, gente, f.desde, f.hasta)
    return t, quien, head, rows


def vista_previa(db: Session, user: User, f: Filtros) -> dict[str, Any]:
    """«Se descargará: … · N filas» before downloading."""
    t, quien, _head, rows = _construir(db, user, f)
    return {
        "filas": len(rows),
        "texto": f"{t.titulo} · {quien} · {_fd(f.desde)} al {_fd(f.hasta)}",
        "archivo": _archivo(t, quien, f),
    }


def descargar(db: Session, user: User, f: Filtros) -> tuple[str, str, int]:
    t, quien, head, rows = _construir(db, user, f)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(head)
    w.writerows(rows)
    nombre = _archivo(t, quien, f)
    db.add(
        ConfigEvento(
            seccion=SECCION,
            actor_id=user.id,
            antes={},
            despues={
                "descarga": t.titulo,
                "quien": quien,
                "periodo": f"{_fd(f.desde)} al {_fd(f.hasta)}",
                "archivo": nombre,
            },
            detalle=f"{len(rows)} filas",
        )
    )
    db.flush()
    return "﻿" + buf.getvalue(), nombre, len(rows)  # BOM so Excel shows the accents


def opciones(db: Session, user: User) -> dict[str, Any]:
    """Tabs, people and cargo groups this person can download, and their recent downloads."""
    ensure(user)
    gente = [
        u
        for u in db.scalars(select(User).where(User.is_active).order_by(User.full_name)).unique()
        if u.id != user.id or user.cargo != Cargo.COORDINACION
    ]
    recientes = db.scalars(
        select(ConfigEvento)
        .where(ConfigEvento.seccion == SECCION, ConfigEvento.actor_id == user.id)
        .order_by(ConfigEvento.created_at.desc())
        .limit(6)
    ).unique()
    return {
        "tipos": [
            {
                "key": t.key,
                "titulo": t.titulo,
                "contenido": t.contenido,
                "disponible": t.disponible,
                "grupos": sorted(grupos_de(user, t), key=list(GRUPOS).index),
            }
            for t in TIPOS.values()
        ],
        "grupos": GRUPOS,
        "personas": [{"id": u.id, "full_name": u.full_name, "grupo": grupo(u)} for u in gente],
        "recientes": [
            {
                "at": e.created_at,
                "archivo": e.despues.get("archivo"),
                "texto": " · ".join(
                    str(e.despues[k]) for k in ("descarga", "quien", "periodo") if e.despues.get(k)
                ),
                "filas": e.detalle,
            }
            for e in recientes
        ],
    }
