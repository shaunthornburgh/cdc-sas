"""Demo comunicados and «Mi agenda» items (G09), called from app.scripts.seed at the end.

System avisos aren't seeded: they come from the data of the other modules the first time each
person opens «Avisos» or the bell polls (unassigned leads, captaciones to verify, GPS, salaries…).

* Gerencia sends a high-priority comunicado to everyone (it goes to the bell); two people read it.
* Coordinación sends a normal one to asesores and Atención y Preventa («Resumen del día»).
* G09's example agenda items, each in its owner's agenda, from today to next week.
"""

from datetime import time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AgendaItem, Aviso, Comunicado
from app.services import avisos as svc
from app.services import fechas
from app.services.users import get_user_by_email

AGENDA = [
    # email, days from today, time, title, note, priority, done
    (
        "gerencia",
        1,
        time(9, 0),
        "Reunión con Coordinación · plan para subir captación",
        None,
        "alta",
        False,
    ),
    ("gerencia", 4, time(8, 0), "Revisar el informe para los socios", None, "normal", False),
    ("coordinacion", 0, time(16, 0), "Revisar las rutas de la semana", None, "normal", False),
    (
        "coordinacion",
        2,
        time(10, 0),
        "Revisar las justificaciones de GPS",
        "2 sin justificar",
        "normal",
        False,
    ),
    (
        "auxiliar",
        0,
        time(15, 0),
        "Enviar el reporte de arriendos a la alcaldía de Sabaneta",
        None,
        "alta",
        False,
    ),
    ("auxiliar", 5, time(11, 0), "Archivar los contratos de septiembre", None, "normal", False),
    (
        "asesor",
        1,
        time(8, 0),
        "Llevar las llaves de INM-0340 a la oficina",
        "Las tiene el propietario hasta el lunes",
        "normal",
        False,
    ),
    (
        "atencion",
        1,
        time(9, 0),
        "Actualizar las respuestas rápidas de WhatsApp",
        None,
        "normal",
        False,
    ),
    ("diego", 0, time(9, 30), "Llevar volantes a la portería de INM-0371", None, "normal", True),
]


def seed_avisos(db: Session) -> int:
    if db.scalar(select(Comunicado.id).limit(1)):
        return 0
    emails = {e for e, *_ in AGENDA} | {"bruno"}
    u = {k: get_user_by_email(db, f"{k}@example.com") for k in emails}
    if None in u.values():
        raise RuntimeError("Seed the demo users first.")
    hoy = fechas.local_date(fechas.now())

    c, _ = svc.enviar_comunicado(
        db,
        {
            "titulo": "Reunión general el viernes a las 8:00 a. m.",
            "cuerpo": "Revisamos los resultados de octubre y el plan de noviembre. Es presencial "
            "en la oficina principal; quien esté en campo se conecta por videollamada.",
            "audiencia": list(svc.AUDIENCIAS),
            "prioridad": "alta",
            "expira_el": hoy + timedelta(days=6),
        },
        actor=u["gerencia"],
    )
    c2, _ = svc.enviar_comunicado(
        db,
        {
            "titulo": "Zonas de captación de noviembre",
            "cuerpo": "Este mes reforzamos Belén y Laureles. Las rutas ya están en «Mi ruta»; si "
            "una zona no te corresponde, recházala con el motivo.",
            "audiencia": ["asesores", "atencion"],
            "prioridad": "normal",
        },
        actor=u["coordinacion"],
    )
    now = fechas.now()
    for com, quienes in ((c, ("coordinacion", "auxiliar")), (c2, ("asesor", "bruno"))):
        for a in db.scalars(select(Aviso).where(Aviso.comunicado_id == com.id)).unique():
            if a.destinatario_id in {u[q].id for q in quienes}:
                a.leido_at = now
                if a.requiere_accion:
                    a.estado, a.atendido_at, a.atendido_por_id = "atendido", now, a.destinatario_id

    for email, dias, hora, titulo, nota, prio, hecha in AGENDA:
        db.add(
            AgendaItem(
                user_id=u[email].id,
                creado_por_id=u[email].id,
                fecha=hoy + timedelta(days=dias),
                hora=hora,
                titulo=titulo,
                nota=nota,
                prioridad=prio,
                estado="hecha" if hecha else "pendiente",
                hecha_at=now if hecha else None,
            )
        )
    db.flush()
    return db.scalar(select(func.count()).select_from(AgendaItem)) or 0
