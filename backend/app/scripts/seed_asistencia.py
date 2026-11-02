"""Demo asistencia (Z04 · K17 · X08), called from app.scripts.seed after rutas and compensación.

Sedes: the main one (Guayabal, 100 m) and «Punto de atención Envigado» (no one assigned). Two weeks
of entradas and salidas for everyone who marks, with the prototype's cases: on time, leve, grave,
outside the location accepted, rejected and marked again, horas extra accepted and an early exit.
Today (if it's a working day and past 8:00): most marked; Pre-ventas outside the sede pending
review, Carla not marked. Yesterday: Diego's horas extra and Bruno's early exit pending.
Unconfirmed salary periods are recalculated with the minutes. DATOS DE EJEMPLO.
"""

from datetime import datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LiquidacionSalario, Marcacion, SalarioConfig, Sede
from app.models.enums import EstadoSalario
from app.services import asistencia, fechas, novedades
from app.services.users import get_user_by_email

PRINCIPAL = (6.2117, -75.5850)
QUIENES = ["asesor", "bruno", "carla", "diego", "preventas", "atencion", "coordinacion", "auxiliar"]
# minutes after 8:00 for each person, cycling through the days (negative = before)
PATRON = {
    "asesor": [-4, -2, 6, -3, -1, -5, 12, -2, -3, -4],
    "bruno": [-2, -3, -1, -4, 3, -2, -6, -1, -2, -3],
    "carla": [-1, 7, -2, 14, -3, -1, 5, -2, -1, -4],
    "diego": [-5, -3, -2, -1, -4, 7, -2, -3, -5, -1],
    "preventas": [-2, -1, 9, -3, -2, -1, -4, -2, 11, -3],
    "atencion": [-1, -2, -3, -1, -2, -4, -1, -3, -2, -1],
    "coordinacion": [-10, -8, -12, -9, -7, -11, -10, -8, -9, -10],
    "auxiliar": [-5, -6, -4, -7, -5, -3, -6, -5, -4, -6],
}


def _dt(d, h: int, m: int) -> datetime:
    return datetime.combine(d, time(0, 0), tzinfo=fechas.BOGOTA) + timedelta(hours=h, minutes=m)


def seed_asistencia(db: Session) -> int:
    if db.scalar(select(Sede.id).limit(1)) is not None:
        return 0
    aux = get_user_by_email(db, "auxiliar@example.com")
    coord = get_user_by_email(db, "coordinacion@example.com")
    db.add(
        Sede(
            nombre="Sede principal",
            direccion="Dirección de ejemplo · Cl 10 Sur # 50-28, Guayabal, Medellín",
            lat=PRINCIPAL[0],
            lng=PRINCIPAL[1],
            radio_m=100,
            principal=True,
            created_by_id=aux.id,
        )
    )
    db.add(
        Sede(
            nombre="Punto de atención Envigado",
            direccion="Dirección de ejemplo · Cra 43A # 38 Sur-35, Envigado",
            lat=6.1719,
            lng=-75.5868,
            radio_m=100,
            created_by_id=aux.id,
        )
    )
    db.flush()
    gente = {k: get_user_by_email(db, f"{k}@example.com") for k in QUIENES}
    now = fechas.now()
    hoy = fechas.local_date(now)
    dias = []
    d = hoy - timedelta(days=1)
    while len(dias) < 10:
        if asistencia.horario(db, d) is not None:
            dias.append(d)
        d -= timedelta(days=1)
    n = 0
    for i, dia in enumerate(reversed(dias)):
        ent_h, sal_h = asistencia.horario(db, dia)
        ayer = dia == dias[0]
        for k, u in gente.items():
            if u is None:
                continue
            tarde = PATRON[k][i % 10]
            entrada = _dt(dia, ent_h.hour, ent_h.minute + tarde)
            lug = asistencia.lugar(db, u, entrada)
            m = Marcacion(
                user_id=u.id,
                fecha=dia,
                asignada=lug.txt,
                entrada_at=entrada,
                entrada_lat=PRINCIPAL[0],
                entrada_lng=PRINCIPAL[1],
                entrada_lugar=f"{lug.nombre} ✓",
                entrada_dentro=True,
                minutos_tarde=max(0, tarde),
                entrada_estado="impuntual" if tarde > 0 else "a_tiempo",
            )
            salida = _dt(dia, sal_h.hour, sal_h.minute + (i % 3))
            m.salida_at, m.salida_tipo, m.salida_estado = salida, "marcada", "ok"
            # The prototype's cases
            if k == "carla" and i == 2:
                m.entrada_lugar, m.entrada_dentro, m.entrada_estado = "A 900 m ✕", False, "aceptada"
                m.entrada_motivo, m.entrada_texto = (
                    "cambio_solicitado",
                    "Coordinación me pidió pasar por un inmueble",
                )
                m.entrada_revisada_por_id, m.entrada_revisada_at = (
                    coord.id,
                    entrada + timedelta(minutes=20),
                )
                m.minutos_tarde = 0
            if k == "preventas" and i == 5:
                m.entrada_lugar, m.entrada_dentro, m.entrada_estado = (
                    "A 2,4 km ✕",
                    False,
                    "rechazada",
                )
                m.entrada_motivo, m.entrada_texto = (
                    "imprevisto",
                    "Me quedé en una diligencia personal",
                )
                m.entrada_revisada_por_id = coord.id
            if k == "diego" and i == 4:
                m.salida_at = _dt(dia, sal_h.hour + 1, sal_h.minute + 10)
                m.salida_tipo, m.salida_estado, m.minutos_extra = "extra", "aceptada", 70
                m.extra_coord = m.extra_aux = True
                m.salida_texto = "Cierre de una promesa con el cliente"
            if k == "bruno" and i == 7:
                m.salida_at = _dt(dia, sal_h.hour - 1, sal_h.minute)
                m.salida_tipo, m.salida_estado, m.minutos_antes = "anticipada", "aceptada", 60
                m.salida_motivo, m.salida_texto = (
                    "permiso",
                    "Cita médica, autorizada por Coordinación",
                )
            if ayer and k == "diego":
                m.salida_at = _dt(dia, sal_h.hour + 1, sal_h.minute + 10)
                m.salida_tipo, m.salida_estado, m.minutos_extra = "extra", "por_aprobar", 70
                m.salida_texto = "Cierre de la promesa de un negocio con el cliente"
            if ayer and k == "bruno":
                m.salida_at = _dt(dia, sal_h.hour - 1, sal_h.minute - 30)
                m.salida_tipo, m.salida_estado, m.minutos_antes = "anticipada", "por_aprobar", 90
                m.salida_motivo, m.salida_texto = (
                    "permiso",
                    "Trámite personal, autorizado ayer por Coordinación",
                )
            db.add(m)
            n += 1
    # Today, if the day has started
    h = asistencia.horario(db, hoy)
    if h and now >= _dt(hoy, h[0].hour, h[0].minute - 10):
        hoy_cases = {
            "asesor": -4,
            "bruno": -2,
            "diego": 7,
            "atencion": -1,
            "coordinacion": -10,
            "auxiliar": -5,
            "preventas": 15,
        }
        for k, tarde in hoy_cases.items():
            u = gente.get(k)
            entrada = min(now, _dt(hoy, h[0].hour, h[0].minute + tarde))
            lug = asistencia.lugar(db, u, entrada)
            m = Marcacion(
                user_id=u.id,
                fecha=hoy,
                asignada=lug.txt,
                entrada_at=entrada,
                entrada_lat=PRINCIPAL[0],
                entrada_lng=PRINCIPAL[1],
                entrada_lugar=f"{lug.nombre} ✓",
                entrada_dentro=True,
                minutos_tarde=max(0, tarde),
                entrada_estado="impuntual" if tarde > 0 else "a_tiempo",
            )
            if k == "preventas":
                m.entrada_lugar, m.entrada_dentro, m.entrada_estado = (
                    "A 1,8 km ✕",
                    False,
                    "por_aprobar",
                )
                m.entrada_motivo, m.entrada_texto = (
                    "imprevisto",
                    "Cierre de vía en la ruta del bus; llego en 20 minutos",
                )
            db.add(m)
            n += 1
    db.flush()
    # Unconfirmed pay periods take the minutes
    for liq in db.scalars(
        select(LiquidacionSalario).where(LiquidacionSalario.estado == EstadoSalario.POR_CONFIRMAR)
    ):
        c = db.get(SalarioConfig, liq.user_id)
        if c is not None:
            novedades.aplicar(db, liq, c.salario_mensual)
    db.flush()
    return n
