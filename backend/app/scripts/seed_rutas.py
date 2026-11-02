"""Demo rutas (G-083 · M04 · X08), called from app.scripts.seed.

Coordinación's routes for the two asesores with Captación, in every state: an accepted route this
week (with today's first arrival marked) and one pending for next week for Asesor Demo; an accepted
route for the whole month (rated 4 by Gerencia) and a rejected one for Bruno; a past week rated 5.
Dates are relative to today. DATOS DE EJEMPLO.
"""

from datetime import datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ruta, RutaEvento, RutaLlegada, RutaZona
from app.services import fechas
from app.services import rutas as svc
from app.services.users import get_user_by_email

LV, LS = [1, 2, 3, 4, 5], [1, 2, 3, 4, 5, 6]


def _z(zona: str, h1: str, h2: str, dias: list[int], orden: int) -> RutaZona:
    a, b = (time.fromisoformat(h) for h in (h1, h2))
    return RutaZona(zona=zona, hora_inicio=a, hora_fin=b, dias=dias, orden=orden)


def seed_rutas(db: Session) -> int:
    if db.scalar(select(Ruta.id).limit(1)) is not None:
        return 0
    coord = get_user_by_email(db, "coordinacion@example.com")
    ger = get_user_by_email(db, "gerencia@example.com")
    ase = get_user_by_email(db, "asesor@example.com")
    bruno = get_user_by_email(db, "bruno@example.com")
    if not all((coord, ger, ase, bruno)):
        raise RuntimeError("Seed the demo users first.")
    now = fechas.now()
    hoy = fechas.local_date(now)
    lunes = hoy - timedelta(days=hoy.weekday())
    mes1 = hoy.replace(day=1)
    mes2 = (mes1 + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    def ruta(
        asesor,
        d1,
        d2,
        dias,
        zonas,
        obs,
        estado,
        origen="manual",
        motivo=None,
        texto=None,
        nota=None,
    ):
        r = Ruta(
            asesor_id=asesor.id,
            desde=d1,
            hasta=d2,
            dias=dias,
            observacion=obs,
            origen=origen,
            estado=estado,
            motivo=motivo,
            motivo_texto=texto,
            creado_por_id=coord.id,
            respondida_at=now - timedelta(hours=20) if estado != "por_aceptar" else None,
        )
        r.zonas.extend(zonas)
        db.add(r)
        db.flush()
        db.add(
            RutaEvento(
                ruta_id=r.id,
                accion="Asignó la ruta",
                despues=f"{asesor.full_name} · {svc.resumen(r)}",
                actor_id=coord.id,
            )
        )
        if estado in ("aceptada", "rechazada"):
            db.add(
                RutaEvento(
                    ruta_id=r.id,
                    accion="Aceptó la ruta" if estado == "aceptada" else "Rechazó la ruta",
                    antes="Por aceptar",
                    despues="Aceptada" if estado == "aceptada" else svc.MOTIVOS[motivo],
                    actor_id=asesor.id,
                )
            )
        if nota:
            r.calificacion, r.calificada_at, r.calificada_por_id = (
                nota,
                now - timedelta(hours=2),
                ger.id,
            )
            db.add(
                RutaEvento(
                    ruta_id=r.id, accion="Calificó la ruta", despues=f"{nota} de 5", actor_id=ger.id
                )
            )
        return r

    semana = ruta(
        ase,
        lunes,
        lunes + timedelta(days=4),
        LV,
        [_z("Laureles", "08:30", "12:00", LV, 0), _z("Belén", "14:00", "17:00", [1, 3, 5], 1)],
        "Captación de apartamentos en oferta",
        "aceptada",
    )
    ruta(
        ase,
        lunes + timedelta(days=7),
        lunes + timedelta(days=11),
        LV,
        [_z("El Poblado", "08:00", "12:00", LV, 0), _z("Guayabal", "14:00", "17:00", [2, 4], 1)],
        "Apoyo a captación Poblado",
        "por_aceptar",
        origen="excel",
    )
    ruta(
        ase,
        lunes - timedelta(days=7),
        lunes - timedelta(days=3),
        LV,
        [_z("Belén", "08:00", "12:00", LV, 0)],
        "Ruta de la semana pasada",
        "aceptada",
        nota=5,
    )
    ruta(
        bruno,
        mes1,
        mes2,
        LS,
        [
            _z("Envigado", "08:00", "11:00", [1, 3, 5], 0),
            _z("Sabaneta", "11:30", "14:00", [1, 3, 5], 1),
            _z("Guayabal", "08:00", "13:00", [2, 4, 6], 2),
        ],
        "Ruta del mes",
        "aceptada",
        nota=4,
    )
    ruta(
        bruno,
        mes2 + timedelta(days=8),
        mes2 + timedelta(days=12),
        LV,
        [_z("Laureles", "08:00", "12:00", LV, 0)],
        None,
        "rechazada",
        motivo="permiso",
        texto="Tengo permiso aprobado esos días",
    )
    db.flush()
    # Today's first arrival on Asesor Demo's route (if today is in it)
    if hoy.isoweekday() in LV and semana.desde <= hoy <= semana.hasta:
        z = semana.zonas[0]
        llegada = min(now, datetime.combine(hoy, time(8, 27), tzinfo=fechas.BOGOTA))
        db.add(RutaLlegada(zona_id=z.id, fecha=hoy, llegada_at=llegada))
    db.flush()
    return 5
