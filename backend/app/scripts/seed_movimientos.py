"""Demo GPS alerts and field work (K05), called from app.scripts.seed after leads and inmuebles.

Mirrors K05-ger's example log over the last 30 days: salidas de ruta and tiempos detenidos of the
asesores with Captación (asesor@ = «Juan», bruno@), the Coordinador's field work and his alerts
(reviewed by Gerencia) and Atención y Preventa supporting a cita. Today's rows are what K05's
Coordinación view shows: one alert to justify, one to review, one approved.

Rows are written directly (the GPS would report them at their time); justifications and reviews
are stored the way the service stores them, with matching history events.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Movimiento, User
from app.models.enums import ActividadCampo as AC
from app.models.enums import EstadoMovimiento as E
from app.models.enums import MotivoMovimiento as M
from app.models.enums import TipoCampo as TC
from app.models.enums import TipoEventoMovimiento as EV
from app.models.enums import TipoMovimiento as T
from app.services import fechas
from app.services import movimientos as svc
from app.services.users import get_user_by_email

LUGARES = {
    "Laureles": (6.2447, -75.5916),
    "El Poblado": (6.2088, -75.5674),
    "Envigado": (6.1719, -75.5866),
    "Belén": (6.2306, -75.6040),
    "Itagüí": (6.1726, -75.6113),
    "Sabaneta": (6.1515, -75.6164),
    "Robledo": (6.2780, -75.5960),
}

# who, days ago, "H:MM", tipo, lugar, estado, justification (motivo, inmueble, cliente / texto)
ALERTAS = [
    ("asesor", 0, "13:12", T.TIEMPO_DETENIDO, "Belén", E.SIN_JUSTIFICAR, None),
    (
        "asesor",
        0,
        "11:05",
        T.SALIDA_RUTA,
        "Laureles",
        E.POR_REVISAR,
        (M.CITA_FUERA_RUTA, "INM-0351", "Cliente Ejemplo 17"),
    ),
    (
        "bruno",
        0,
        "10:20",
        T.TIEMPO_DETENIDO,
        "Envigado",
        E.APROBADA,
        (M.CITA_NO_PROGRAMADA, "INM-0362", "Propietario Ejemplo 4"),
    ),
    (
        "asesor",
        0,
        "9:40",
        T.SALIDA_RUTA,
        "El Poblado",
        E.APROBADA,
        (M.PERMISO_PERSONAL, "Trámite personal", "coordinacion"),
    ),
    ("coordinacion", 0, "11:10", T.SALIDA_ZONA, "Itagüí", E.SIN_JUSTIFICAR, None),
    (
        "coordinacion",
        1,
        "15:40",
        T.TIEMPO_DETENIDO,
        "Belén",
        E.POR_REVISAR,
        (M.INVENTARIO, "INM-0318", "Juan Ejemplo"),
    ),
    (
        "asesor",
        2,
        "8:50",
        T.SALIDA_RUTA,
        "Robledo",
        E.RECHAZADA,
        (M.CITA_FUERA_RUTA, "INM-0351", "Cliente Ejemplo 9"),
    ),
    (
        "asesor",
        9,
        "14:30",
        T.SALIDA_RUTA,
        "Sabaneta",
        E.APROBADA,
        (M.CITA_FUERA_RUTA, "INM-0301", "Cliente Ejemplo 3"),
    ),
    (
        "asesor",
        18,
        "11:05",
        T.SALIDA_RUTA,
        "Laureles",
        E.APROBADA,
        (M.INVENTARIO, "INM-0333", "Cliente Ejemplo 5"),
    ),
    (
        "bruno",
        10,
        "13:12",
        T.TIEMPO_DETENIDO,
        "Envigado",
        E.APROBADA,
        (M.IMPREVISTO_PERSONAL, "Llanta pinchada", None),
    ),
    (
        "bruno",
        17,
        "16:20",
        T.TIEMPO_DETENIDO,
        "Itagüí",
        E.RECHAZADA,
        (M.CITA_NO_PROGRAMADA, "INM-0372", "Cliente Ejemplo 11"),
    ),
    (
        "bruno",
        25,
        "10:20",
        T.SALIDA_RUTA,
        "Belén",
        E.APROBADA,
        (M.PERMISO_PERSONAL, "Cita médica", "coordinacion"),
    ),
    (
        "coordinacion",
        8,
        "13:12",
        T.TIEMPO_DETENIDO,
        "Sabaneta",
        E.APROBADA,
        (M.INVENTARIO, "INM-0301", "Ana Ejemplo"),
    ),
    (
        "atencion",
        2,
        "15:20",
        T.TIEMPO_DETENIDO,
        "Envigado",
        E.APROBADA,
        (M.CITA_NO_PROGRAMADA, "INM-0290", "Cliente Ejemplo 4"),
    ),
]

# who, days ago, "H:MM", minutes, tipo de campo, actividad, con (emails), detalle, lugar
CAMPO = [
    (
        "coordinacion",
        0,
        "9:30",
        95,
        TC.ACOMPANAMIENTO_RUTA,
        AC.CAPTACION,
        ["asesor"],
        "sector Laureles",
        "Laureles",
    ),
    ("coordinacion", 2, "14:00", 130, TC.APOYO_CITA, AC.CITA_VENTA, [], "venta", "El Poblado"),
    (
        "coordinacion",
        4,
        "8:30",
        210,
        TC.SALIDA_GRUPAL,
        AC.CAPTACION,
        ["carla", "diego"],
        "sector Belén",
        "Belén",
    ),
    (
        "coordinacion",
        9,
        "9:00",
        165,
        TC.ACOMPANAMIENTO_RUTA,
        AC.CAPTACION,
        ["bruno"],
        "sector Envigado",
        "Envigado",
    ),
    (
        "coordinacion",
        23,
        "8:30",
        180,
        TC.SALIDA_GRUPAL,
        AC.CAPTACION,
        ["asesor", "bruno"],
        "sector Sabaneta",
        "Sabaneta",
    ),
    ("atencion", 2, "15:10", 100, TC.APOYO_CITA, AC.CITA_VENTA, [], None, "Envigado"),
    (
        "atencion",
        13,
        "10:00",
        75,
        TC.OTRA,
        AC.VISITA_PROPIETARIO,
        [],
        "apoyo con propietario",
        "Laureles",
    ),
]


def _at(d: date, hm: str) -> datetime:
    h, m = (int(x) for x in hm.split(":"))
    return datetime.combine(d, time(h, m), tzinfo=fechas.BOGOTA)


def seed_movimientos(db: Session) -> int:
    if db.scalar(select(Movimiento.id).limit(1)):
        return 0
    emails = ("gerencia", "coordinacion", "asesor", "bruno", "carla", "diego", "atencion")
    u: dict[str, User] = {k: get_user_by_email(db, f"{k}@example.com") for k in emails}  # type: ignore[misc]
    if None in u.values():
        raise RuntimeError("Seed the demo users first.")
    cfg = svc.get_config(db)
    now = fechas.now()
    hoy = fechas.local_date(now)

    def nuevo(who: str, dias: int, hm: str, tipo: T, lugar: str, **kw) -> Movimiento:
        cuando = _at(hoy - timedelta(days=dias), hm)
        if cuando > now:  # today's example time is still ahead: use yesterday
            cuando -= timedelta(days=1)
        la, ln = LUGARES[lugar]
        m = Movimiento(
            empleado_id=u[who].id,
            tipo=tipo,
            ocurrido_at=cuando,
            lugar=lugar,
            lat=Decimal(str(la)),
            lng=Decimal(str(ln)),
            creado_por_id=u[who].id,
            minutos_umbral=cfg.minutos_alerta if tipo == T.TIEMPO_DETENIDO else None,
            acompanados_ids=[],
            **kw,
        )
        m.empleado = u[who]
        db.add(m)
        db.flush()
        ev = svc._evento(db, m, EV.CREADO, u[who], detalle="GPS del celular", despues=m.estado)
        ev.created_at = cuando
        return m

    for who, dias, hm, tipo, lugar, estado, just in ALERTAS:
        m = nuevo(who, dias, hm, tipo, lugar, estado=E.SIN_JUSTIFICAR)
        if just is None:
            continue
        motivo, a, b = just
        m.motivo = motivo
        if motivo in svc.MOTIVOS_CON_INMUEBLE:
            m.inmueble_codigo, m.cliente = a, b
            m.observacion = "Atendiendo al cliente en el inmueble"
        else:
            m.motivo_texto, m.autorizo = a, b
        m.justificada_at = m.ocurrido_at + timedelta(minutes=12)
        m.estado = E.POR_REVISAR
        ev = svc._evento(
            db,
            m,
            EV.JUSTIFICADO,
            u[who],
            detalle=svc.detalle_txt(db, m, now),
            antes=E.SIN_JUSTIFICAR,
            despues=E.POR_REVISAR,
        )
        ev.created_at = m.justificada_at
        if estado in (E.APROBADA, E.RECHAZADA):
            rev = u["gerencia"] if who == "coordinacion" else u["coordinacion"]
            m.estado = estado
            m.revisado_por, m.revisado_por_id = rev, rev.id
            m.revisado_at = m.justificada_at + timedelta(hours=1)
            if estado == E.RECHAZADA:
                m.nota_revision = "No coincide con la agenda del día"
            ev = svc._evento(
                db,
                m,
                EV.APROBADO if estado == E.APROBADA else EV.RECHAZADO,
                rev,
                detalle=m.nota_revision,
                antes=E.POR_REVISAR,
                despues=estado,
            )
            ev.created_at = m.revisado_at

    for who, dias, hm, mins, tc, act, con, detalle, lugar in CAMPO:
        tipo = T.TRABAJO_CAMPO if who == "coordinacion" else T.ATENCION_CAMPO
        m = nuevo(
            who,
            dias,
            hm,
            tipo,
            lugar,
            estado=E.REGISTRO,
            tipo_campo=tc,
            actividad_campo=act,
            detalle=detalle,
        )
        m.acompanados_ids = [str(u[c].id) for c in con]
        m.fin_at = m.ocurrido_at + timedelta(minutes=mins)
        ev = svc._evento(
            db,
            m,
            EV.FINALIZADO,
            u[who],
            detalle=f"Duración {svc.fmt_dur(mins)} · GPS apagado",
            antes=E.REGISTRO,
            despues=E.REGISTRO,
        )
        ev.created_at = m.fin_at
    db.flush()
    return db.scalar(select(func.count()).select_from(Movimiento)) or 0
