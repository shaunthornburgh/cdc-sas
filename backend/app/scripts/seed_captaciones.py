"""Demo captaciones for local development (called from app.scripts.seed).

Addresses and owners are fictitious. Everything goes through the service so the history
reads like real use; timestamps are then moved back relative to now.
"""

from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Captacion, CaptacionEvento
from app.models.enums import EstadoCaptacion as E
from app.models.enums import MotivoRechazoCaptacion as M
from app.services import captaciones as svc
from app.services import fechas
from app.services.users import get_user_by_email

NOW = fechas.now()


def ago(**kw) -> datetime:
    return NOW - timedelta(**kw)


def seed_captaciones(db: Session) -> int:
    if db.scalar(select(func.count()).select_from(Captacion)):
        return 0
    u = {k: get_user_by_email(db, f"{k}@example.com") for k in ("asesor", "bruno", "coordinacion")}
    if any(v is None for v in u.values()):
        raise RuntimeError("Seed the demo users first.")

    def step(cap: Captacion | None, when: datetime, fn: Callable[[], Captacion]) -> Captacion:
        before = set(db.scalars(select(CaptacionEvento.id))) if cap else set()
        out = fn()
        db.flush()
        for ev in db.scalars(
            select(CaptacionEvento).where(CaptacionEvento.captacion_id == out.id)
        ).unique():
            if ev.id not in before:
                ev.created_at = when
        return out

    def nueva(who: str, when: datetime, gps=None, **data) -> Captacion:
        data.setdefault("modo", "rapido")
        cap = step(
            None,
            when,
            lambda: svc.create_captacion(db, data, actor=None, asesor_id=u[who].id, gps=gps),
        )
        cap.enviada_at = when
        cap.created_at = when
        if cap.gps_at:
            cap.gps_at = when
        return cap

    def aprobar(cap: Captacion, when: datetime) -> None:
        step(
            cap,
            when,
            lambda: svc.verificar(
                db, cap, E.APROBADA, motivo=None, observacion=None, actor=u["coordinacion"]
            ),
        )
        cap.verificado_at = when

    def rechazar(cap: Captacion, when: datetime, motivo: M, obs: str | None = None) -> None:
        step(
            cap,
            when,
            lambda: svc.verificar(
                db, cap, E.RECHAZADA, motivo=motivo, observacion=obs, actor=u["coordinacion"]
            ),
        )
        cap.verificado_at = when

    def publicar(cap: Captacion, when: datetime, who: str) -> None:
        step(cap, when, lambda: svc.publicar(db, cap, actor=u[who]))
        cap.publicada_at = when

    def gps(lat: float, lng: float, m: int) -> dict:
        return {"lat": lat, "lng": lng, "precision_m": m}

    # ---- Por verificar (hoy y ayer)
    nueva(
        "asesor",
        ago(hours=1, minutes=10),
        gps(6.200612, -75.573498, 40),
        negocio="venta",
        codigo_inmueble="INM-0360",
        direccion="Cl 10 Sur # 43-80, El Poblado, Medellín",
    )
    nueva(
        "bruno",
        ago(hours=2),
        gps(6.151820, -75.616410, 25),
        negocio="venta",
        codigo_inmueble="INM-0358",
        direccion="Cra 43A # 60 Sur-15, Sabaneta",
    )
    nueva(
        "bruno",
        ago(days=1, hours=3),
        gps(6.245310, -75.592870, 18),
        modo="completo",
        negocio="arriendo",
        codigo_inmueble="INM-0371",
        direccion="Cra 76 # 33A-21 apto 402",
        tipo_inmueble="apartamento",
        barrio="Laureles",
        municipio="Medellín",
        precio=2_400_000,
        area_m2=72,
        habitaciones=3,
        banos=2,
        parqueadero=True,
        propietario_nombre="Rosa Elena Múnera",
        propietario_telefono="300 555 0177",
        observaciones="Disponible desde el 1 de noviembre. Prefiere arrendatario sin mascotas.",
    )

    # ---- Aprobadas (una publicada)
    c = nueva(
        "asesor",
        ago(days=4, hours=2),
        gps(6.230440, -75.603980, 30),
        modo="completo",
        negocio="venta",
        codigo_inmueble="INM-0351",
        direccion="Cl 33 # 80-20",
        tipo_inmueble="casa",
        barrio="Belén",
        municipio="Medellín",
        precio=780_000_000,
        area_m2=145,
        habitaciones=4,
        banos=3,
        parqueadero=True,
        propietario_nombre="Hernán Darío Posada",
        propietario_telefono="301 555 0133",
        observaciones="Casa de dos plantas con patio. Escrituras al día.",
    )
    aprobar(c, ago(days=3, hours=6))
    publicar(c, ago(days=2, hours=4), "asesor")

    c = nueva(
        "bruno",
        ago(days=5, hours=1),
        gps(6.168930, -75.585520, 15),
        negocio="venta",
        codigo_inmueble="INM-0350",
        direccion="Cl 37 Sur # 39-10, Envigado",
    )
    aprobar(c, ago(days=4, hours=20))

    c = nueva(
        "bruno",
        ago(days=8),
        gps(6.172240, -75.611340, 35),
        negocio="arriendo",
        codigo_inmueble="INM-0344",
        direccion="Cra 52 # 75-40, Itagüí",
    )
    aprobar(c, ago(days=7, hours=21))
    publicar(c, ago(days=7, hours=2), "bruno")

    # ---- Rechazadas
    c = nueva(
        "asesor",
        ago(days=3, hours=4),
        gps(6.247110, -75.597340, 20),
        negocio="arriendo",
        codigo_inmueble="INM-0355",
        direccion="Cra 70 # 45-12, Laureles",
    )
    rechazar(
        c,
        ago(days=2, hours=22),
        M.CODIGO_NO_CORRESPONDE,
        "En Ciencuadras ese código es un local en Guayabal.",
    )

    c = nueva(
        "bruno",
        ago(days=2, hours=5),
        gps(6.209870, -75.566900, 22),
        negocio="venta",
        codigo_inmueble="INM-0339",
        direccion="Cl 9 # 37-50, El Poblado",
    )
    rechazar(c, ago(days=1, hours=23), M.CODIGO_INEXISTENTE)

    # ---- Rechazada, corregida y reenviada → por verificar otra vez
    c = nueva(
        "bruno",
        ago(days=6),
        gps(6.255340, -75.590120, 28),
        negocio="arriendo",
        codigo_inmueble="INM-0349",
        direccion="Cl 44 # 70-15, Laureles",
    )
    rechazar(c, ago(days=5, hours=20), M.CODIGO_INEXISTENTE)
    step(
        c,
        ago(days=5, hours=2),
        lambda: svc.reenviar(
            db, c, codigo_inmueble="INM-0348", direccion="Cl 44 # 70-15, Laureles", actor=u["bruno"]
        ),
    )
    c.enviada_at = ago(days=5, hours=2)

    db.flush()
    return db.scalar(select(func.count()).select_from(Captacion)) or 0
