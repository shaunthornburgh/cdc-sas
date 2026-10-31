"""Demo leads and citas for local development (called from app.scripts.seed).

Names and phone numbers are fictitious (555 numbers). Times are relative to now so the
«today» views always have something to show. Everything goes through the services, so
the history reads exactly as it would in real use; only timestamps are moved back.
"""

from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Cita, Lead, LeadEvento
from app.models.enums import (
    AccionSeguimiento,
    EstadoCita,
    EtapaLead,
    FuenteLead,
    MedioContacto,
    MotivoPerdida,
    ResultadoLlamada,
    TipoCita,
    TipoEventoLead,
)
from app.services import citas, fechas
from app.services import leads as svc
from app.services.users import get_user_by_email

F = FuenteLead
NOW = fechas.now()


def ago(**kw) -> datetime:
    return NOW - timedelta(**kw)


def ahead(**kw) -> datetime:
    return NOW + timedelta(**kw)


def at_local(days: int, hour: int, minute: int = 0) -> datetime:
    """A local (Bogotá) wall-clock time `days` from today."""
    d = fechas.local_date(NOW) + timedelta(days=days)
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=fechas.BOGOTA)


class Seeder:
    def __init__(self, db: Session):
        self.db = db
        self.u = {
            k: get_user_by_email(db, f"{k}@example.com")
            for k in ("atencion", "preventas", "coordinacion", "asesor", "carla", "diego")
        }

    def step(self, lead: Lead, when: datetime, fn: Callable[[], object]) -> object:
        """Run a service call and date the history lines it wrote at `when`."""
        before = set(self.db.scalars(select(LeadEvento.id).where(LeadEvento.lead_id == lead.id)))
        out = fn()
        self.db.flush()
        for ev in self.db.scalars(select(LeadEvento).where(LeadEvento.lead_id == lead.id)).unique():
            if ev.id not in before:
                ev.created_at = when
        return out

    def lead(self, when: datetime, **data) -> Lead:
        lead = svc.create_lead(self.db, data, actor=None)
        lead.created_at = when
        self.db.flush()
        for ev in self.db.scalars(select(LeadEvento).where(LeadEvento.lead_id == lead.id)).unique():
            ev.created_at = when
        return lead

    def follow(self, lead: Lead, who: str, when: datetime) -> None:
        self.step(lead, when, lambda: svc.follow_lead(self.db, lead, self.u[who]))
        lead.assigned_at = when

    def call(self, lead, who, when, resultado, resumen=None, minutos=None):
        self.step(
            lead,
            when,
            lambda: svc.registrar_llamada(
                self.db,
                lead,
                resultado=resultado,
                resumen=resumen,
                duracion_min=minutos,
                actor=self.u[who],
            ),
        )

    def msg(self, lead, who, when, texto, opciones=False, medio=MedioContacto.WHATSAPP):
        tipo = TipoEventoLead.OPCIONES if opciones else TipoEventoLead.MENSAJE
        self.step(
            lead,
            when,
            lambda: svc.registrar_mensaje(
                self.db, lead, tipo=tipo, medio=medio, texto=texto, actor=self.u[who]
            ),
        )

    def obs(self, lead, who, when, texto):
        self.step(
            lead,
            when,
            lambda: svc.registrar_observacion(self.db, lead, texto=texto, actor=self.u[who]),
        )

    def seg(self, lead, who, when, accion, due, nota=None):
        self.step(
            lead,
            when,
            lambda: svc.programar_seguimiento(
                self.db, lead, accion=accion, due_at=due, nota=nota, actor=self.u[who]
            ),
        )

    def cita(self, lead, who, when, tipo, scheduled, asesor, inmueble=None, notas=None) -> Cita:
        return self.step(
            lead,
            when,
            lambda: citas.create_cita(
                self.db,
                lead,
                tipo=tipo,
                scheduled_at=scheduled,
                asesor_id=self.u[asesor].id,
                inmueble=inmueble,
                notas=notas,
                actor=self.u[who],
            ),
        )

    def estado(self, cita, who, when, estado, motivo=None):
        self.step(
            cita.lead,
            when,
            lambda: citas.set_estado(self.db, cita, estado, motivo=motivo, actor=self.u[who]),
        )


def seed_leads(db: Session) -> int:
    if db.scalar(select(func.count()).select_from(Lead)):
        return 0
    s = Seeder(db)
    if any(v is None for v in s.u.values()):
        raise RuntimeError("Seed the demo users first.")
    A, LL, R = AccionSeguimiento, ResultadoLlamada, EstadoCita

    # ---- Llegaron solos hoy, sin responsable («Leads nuevos»)
    s.lead(
        ago(hours=2),
        full_name="Valentina Ospina",
        phone="300 555 0142",
        fuente=F.FACEBOOK,
        fuente_detalle="Anuncio · Apartamentos Laureles",
        negocio="arriendo",
        busca="Apartamento en Laureles",
        presupuesto="Hasta $2.800.000",
        zona="Laureles",
    )
    s.lead(
        ago(minutes=95),
        full_name="Andrés Cardona",
        phone="301 555 0188",
        fuente=F.CIENCUADRAS,
        negocio="venta",
        busca="Casa en Envigado",
        presupuesto="Hasta $750.000.000",
        zona="Envigado",
        email="andres.cardona@example.com",
    )
    s.lead(
        ago(minutes=40),
        full_name="Luisa Fernanda Ríos",
        phone="310 555 0123",
        fuente=F.PROPPI,
        negocio="arriendo",
        busca="Local en Guayabal",
        zona="Guayabal",
    )
    s.lead(
        ago(minutes=12),
        full_name="Camilo Zapata",
        phone="312 555 0176",
        fuente=F.INSTAGRAM,
        fuente_detalle="Mensaje directo",
        negocio="arriendo",
        busca="Apartaestudio en El Poblado",
        para_cuando="El próximo mes",
    )

    # ---- Atención: en seguimiento después de enviar opciones
    m = s.lead(
        ago(hours=5),
        full_name="Mariana Restrepo",
        phone="300 555 0101",
        email="mariana.restrepo@example.com",
        fuente=F.FACEBOOK,
        fuente_detalle="Formulario «Busco apartamento en Laureles»",
        negocio="arriendo",
        busca="Apartamento de 2 habitaciones",
        presupuesto="Hasta $2.500.000",
        zona="Laureles o Belén",
        para_cuando="Este mes",
    )
    s.follow(m, "atencion", ago(hours=4, minutes=58))
    s.call(m, "atencion", ago(hours=4, minutes=47), LL.NO_CONTESTO)
    s.call(
        m,
        "atencion",
        ago(hours=4, minutes=32),
        LL.CONTESTO,
        "Busca arriendo hasta $2.500.000 en Laureles o Belén, 2 habitaciones, para este mes.",
        6,
    )
    s.msg(
        m,
        "atencion",
        ago(hours=4, minutes=26),
        "Te comparto 3 opciones: Apto Laureles 2 hab $2.400.000 · Apto Belén $2.300.000 · "
        "Apto Laureles con parqueadero $2.500.000.",
        opciones=True,
    )
    s.seg(
        m,
        "atencion",
        ago(hours=4, minutes=25),
        A.LLAMAR,
        ahead(hours=2),
        "Confirmar si le gustó alguna de las 3 opciones",
    )

    # ---- Atención: cita pendiente de aceptación mañana
    sm = s.lead(
        ago(days=1, hours=3),
        full_name="Santiago Mejía",
        phone="315 555 0190",
        fuente=F.CIENCUADRAS,
        negocio="venta",
        busca="Apartamento en El Poblado",
        presupuesto="Hasta $900.000.000",
        zona="El Poblado",
    )
    s.follow(sm, "atencion", ago(days=1, hours=2, minutes=55))
    s.call(
        sm,
        "atencion",
        ago(days=1, hours=2, minutes=50),
        LL.CONTESTO,
        "Quiere ver el apto de 3 habitaciones en El Poblado. Disponible mañana en la mañana.",
        8,
    )
    s.cita(
        sm,
        "atencion",
        ago(days=1, hours=2, minutes=40),
        TipoCita.VISITA_VENTA,
        at_local(1, 10),
        "asesor",
        "INM-0290 · Apto El Poblado",
        "Llega en carro; avisar en portería",
    )

    # ---- Atención: en gestión
    d = s.lead(
        ago(days=1, hours=6),
        full_name="Daniela Torres",
        phone="317 555 0154",
        fuente=F.METROCUADRADO,
        negocio="arriendo",
        busca="Casa en Sabaneta",
        presupuesto="Hasta $3.200.000",
        zona="Sabaneta",
    )
    s.follow(d, "atencion", ago(days=1, hours=5, minutes=50))
    s.call(
        d,
        "atencion",
        ago(days=1, hours=5, minutes=40),
        LL.CONTESTO,
        "Tiene 2 perros: necesita casa con patio. Puede pagar hasta $3.200.000.",
        5,
    )
    s.obs(
        d,
        "atencion",
        ago(days=1, hours=5, minutes=35),
        "Prefiere que la contacten después de las 3 p. m.",
    )

    # ---- Atención: cita rechazada por la asesora → requiere acción
    j = s.lead(
        ago(days=1, hours=1),
        full_name="Julián Henao",
        phone="318 555 0137",
        fuente=F.TIKTOK,
        negocio="arriendo",
        busca="Apartamento en Belén",
        zona="Belén",
    )
    s.follow(j, "atencion", ago(days=1))
    s.call(
        j,
        "atencion",
        ago(hours=23),
        LL.CONTESTO,
        "Le interesa el apto de Belén. Puede mañana en la tarde.",
        4,
    )
    cj = s.cita(
        j,
        "atencion",
        ago(hours=22),
        TipoCita.VISITA_ARRIENDO,
        at_local(1, 16),
        "carla",
        "INM-0318 · Apto Belén",
    )
    s.estado(cj, "atencion", ago(hours=3), R.RECHAZADA, "Choque con otra cita de inventario.")

    # ---- Atención: cita aceptada hoy
    p = s.lead(
        ago(days=2, hours=2),
        full_name="Paula Vélez",
        phone="320 555 0109",
        fuente=F.FINCA_RAIZ,
        negocio="venta",
        busca="Casa en Sabaneta",
        presupuesto="Hasta $600.000.000",
        zona="Sabaneta",
    )
    s.follow(p, "atencion", ago(days=2, hours=1, minutes=50))
    s.call(
        p,
        "atencion",
        ago(days=2, hours=1, minutes=45),
        LL.CONTESTO,
        "Quiere visitar la casa de Sabaneta.",
        7,
    )
    cp = s.cita(
        p,
        "atencion",
        ago(days=2, hours=1, minutes=30),
        TipoCita.VISITA_VENTA,
        ahead(hours=3),
        "diego",
        "INM-0342 · Casa Sabaneta",
    )
    s.estado(cp, "atencion", ago(days=2, hours=1), R.ACEPTADA)

    # ---- Atención: 3 llamadas sin contestar en 3 días seguidos (no descontaría)
    e = s.lead(
        ago(days=3, hours=4),
        full_name="Esteban Gil",
        phone="321 555 0165",
        fuente=F.FACEBOOK,
        negocio="arriendo",
        busca="Apartamento en Envigado",
    )
    s.follow(e, "atencion", ago(days=3, hours=3, minutes=55))
    for day in (3, 2, 1):
        s.call(e, "atencion", ago(days=day, hours=3), LL.NO_CONTESTO)
    s.seg(
        e,
        "atencion",
        ago(days=1, hours=2, minutes=58),
        A.VOLVER_A_CONTACTAR,
        ahead(days=1),
        "Último intento antes de marcar perdido",
    )

    # ---- Pre-ventas: en gestión (mensaje enviado)
    n = s.lead(
        ago(hours=7),
        full_name="Natalia Quintero",
        phone="322 555 0118",
        fuente=F.ESPACIO_URBANO,
        negocio="venta",
        busca="Lote en Rionegro",
        zona="Rionegro",
    )
    s.follow(n, "preventas", ago(hours=6, minutes=50))
    s.msg(
        n,
        "preventas",
        ago(hours=6, minutes=45),
        "Hola Natalia, soy de Casa Dolce Casa. ¿Te puedo llamar en unos minutos?",
    )

    # ---- Pre-ventas: cita en menos de 1 hora sin aceptar → requiere acción
    fa = s.lead(
        ago(hours=6),
        full_name="Felipe Arango",
        phone="323 555 0193",
        fuente=F.PROPPI,
        negocio="arriendo",
        busca="Apartamento en Laureles",
    )
    s.follow(fa, "preventas", ago(hours=5, minutes=55))
    s.call(fa, "preventas", ago(hours=5, minutes=50), LL.CONTESTO, "Quiere verlo hoy mismo.", 3)
    s.cita(
        fa,
        "preventas",
        ago(hours=5, minutes=45),
        TipoCita.VISITA_ARRIENDO,
        ahead(minutes=45),
        "carla",
        "INM-0333 · Apto Laureles",
    )

    # ---- Archivados: un perdido y un ganado
    c = s.lead(
        ago(days=6),
        full_name="Carolina Duque",
        phone="324 555 0126",
        fuente=F.FACEBOOK,
        negocio="arriendo",
        busca="Apartamento en El Poblado",
    )
    s.follow(c, "atencion", ago(days=6) + timedelta(minutes=8))
    s.call(
        c,
        "atencion",
        ago(days=6) + timedelta(minutes=15),
        LL.CONTESTO,
        "Su presupuesto es $1.500.000; en El Poblado no hay opciones en ese rango.",
        4,
    )
    s.step(
        c,
        ago(days=5),
        lambda: svc.change_stage(
            db, c, EtapaLead.PERDIDO, motivo=MotivoPerdida.PRESUPUESTO, actor=s.u["atencion"]
        ),
    )

    g = s.lead(
        ago(days=9),
        full_name="Sebastián Correa",
        phone="325 555 0147",
        fuente=F.CIENCUADRAS,
        negocio="arriendo",
        busca="Apartamento en Laureles",
    )
    s.follow(g, "atencion", ago(days=9) + timedelta(minutes=5))
    s.call(
        g, "atencion", ago(days=9) + timedelta(minutes=20), LL.CONTESTO, "Listo para visitar.", 5
    )
    cg = s.cita(
        g,
        "atencion",
        ago(days=9) + timedelta(minutes=30),
        TipoCita.VISITA_ARRIENDO,
        ahead(days=30),
        "carla",
        "INM-0333 · Apto Laureles",
    )
    s.estado(cg, "atencion", ago(days=9) + timedelta(hours=1), R.ACEPTADA)
    cg.scheduled_at = ago(days=7)
    s.estado(
        cg,
        "atencion",
        ago(days=7) + timedelta(hours=2),
        R.REALIZADA,
        "Le gustó el apartamento; pasa a negocio.",
    )
    s.step(
        g,
        ago(days=2),
        lambda: svc.change_stage(db, g, EtapaLead.GANADO, motivo=None, actor=s.u["coordinacion"]),
    )

    db.flush()
    return db.scalar(select(func.count()).select_from(Lead)) or 0
