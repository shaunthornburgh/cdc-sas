"""Demo month of work so «Mis resultados», «Mi equipo» and «Rendimiento de la empresa» show numbers.

Called from app.scripts.seed. Clients are fictitious. These are back-dated history rows (deals
closed, captaciones approved, calls made earlier this month and last month), so they are inserted
directly instead of through the services, which only accept actions happening now.

Rough targets (prototype figures): Asesor ~78 %, Bruno 85 %, Carla ~62 %, Diego ~83 %,
Atención ~85 %, Pre-ventas ~70 %.
"""

from datetime import datetime, timedelta
from itertools import count

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Calificacion,
    Captacion,
    Cita,
    Lead,
    LeadEvento,
    RendimientoConfig,
    Seguimiento,
    User,
)
from app.models.enums import (
    AccionSeguimiento,
    EstadoCaptacion,
    EstadoCita,
    EtapaLead,
    FuenteLead,
    ModoCaptacion,
    MotivoPerdida,
    TipoCita,
    TipoEventoLead,
    TipoNegocio,
)
from app.services import fechas
from app.services import rendimiento as rend
from app.services.users import get_user_by_email

V, A = TipoNegocio.VENTA, TipoNegocio.ARRIENDO
ZONAS = ["Laureles", "Envigado", "Belén", "El Poblado", "Sabaneta", "Robledo", "Itagüí"]
NOMBRES = (
    "Camila Restrepo, Santiago Gómez, Valentina Arias, Mateo Londoño, Isabella Cardona, "
    "Samuel Duque, Mariana Zapata, Tomás Echeverri, Sara Villegas, Emilio Ossa, Luciana Mejía, "
    "Martín Uribe, Antonia Correa, Jerónimo Toro, Salomé Ríos, Simón Quintero, Gabriela Vélez, "
    "Nicolás Henao, Manuela Posada, Juan José Mesa, Laura Sofía Gil, Andrés Felipe Cano, "
    "Paula Andrea Muñoz, Esteban Ochoa, María José Pérez, David Alzate, Daniela Hoyos, "
    "Sebastián Marín, Catalina Franco, Alejandro Montoya, Juliana Builes, Felipe Zuluaga"
).split(", ")


def seed_rendimiento(db: Session) -> int:
    if db.scalar(select(func.count()).select_from(RendimientoConfig)):
        return 0
    keys = (
        "asesor",
        "bruno",
        "carla",
        "diego",
        "atencion",
        "preventas",
        "coordinacion",
        "gerencia",
    )
    u: dict[str, User] = {k: get_user_by_email(db, f"{k}@example.com") for k in keys}  # type: ignore[misc]
    if any(v is None for v in u.values()):
        raise RuntimeError("Seed the demo users first.")

    now = fechas.now()
    cur = rend.periodo()
    prev = cur.anterior()
    codes = count(7001)
    names = iter(NOMBRES * 4)
    created = 0

    def at(p: rend.Periodo, frac: float) -> datetime:
        """A moment at «frac» of the way through the month (never after now)."""
        end = min(p.end, now - timedelta(minutes=30))
        return p.start + (end - p.start) * frac

    def spread(p: rend.Periodo, n: int, lo: float = 0.05, hi: float = 0.95) -> list[datetime]:
        return [at(p, lo + (hi - lo) * i / max(n - 1, 1)) for i in range(n)]

    def lead(
        when: datetime,
        negocio,
        atiende: User | None,
        etapa=EtapaLead.EN_GESTION,
        cierre: datetime | None = None,
        **kw,
    ) -> Lead:
        nonlocal created
        created += 1
        ld = Lead(
            full_name=next(names),
            phone=f"300 555 {7000 + created:04d}",
            fuente=FuenteLead.OTRO,
            fuente_detalle="Demo rendimiento",
            negocio=negocio,
            busca=("Apartamento" if negocio == A else "Casa")
            + f" en {ZONAS[created % len(ZONAS)]}",
            zona=ZONAS[created % len(ZONAS)],
            etapa=etapa,
            assigned_to_id=atiende.id if atiende else None,
            assigned_at=when if atiende else None,
            created_by_id=(atiende or u["coordinacion"]).id,
            cerrado_at=cierre,
            **kw,
        )
        ld.created_at = ld.updated_at = when
        db.add(ld)
        db.flush()
        return ld

    def evento(ld: Lead, tipo, who: User, when: datetime, titulo: str, **datos) -> None:
        db.add(
            LeadEvento(
                lead_id=ld.id,
                tipo=tipo,
                titulo=titulo,
                datos=datos,
                created_by_id=who.id,
                created_at=when,
            )
        )

    def llamadas(ld: Lead, who: User, when: datetime, n: int, contesta: bool = True) -> None:
        for i in range(n):
            ok = contesta and i == n - 1
            evento(
                ld,
                TipoEventoLead.LLAMADA,
                who,
                when + timedelta(hours=2 * i),
                "Llamada · contestó" if ok else "Llamada · no contestó",
                resultado="contesto" if ok else "no_contesto",
                intento=i + 1,
            )

    def cita(ld: Lead, asesor: User, who: User, when: datetime, visita: datetime) -> None:
        tipo = TipoCita.VISITA_VENTA if ld.negocio == V else TipoCita.VISITA_ARRIENDO
        c = Cita(
            lead_id=ld.id,
            tipo=tipo,
            scheduled_at=visita,
            asesor_id=asesor.id,
            estado=EstadoCita.REALIZADA,
            inmueble="Inmueble de ejemplo",
            motivo="Le gustó; pidió los documentos",
            created_by_id=who.id,
        )
        c.created_at = c.updated_at = when
        db.add(c)
        evento(ld, TipoEventoLead.CITA, who, when, f"Cita programada con {asesor.full_name}")

    def ganado(p: rend.Periodo, frac: float, negocio, asesor: User, atiende: User | None) -> None:
        when = at(p, frac)
        ld = lead(when, negocio, atiende, EtapaLead.GANADO, cierre=at(p, frac + 0.04))
        quien = atiende or u["coordinacion"]
        llamadas(ld, quien, when, 1)
        cita(ld, asesor, quien, when, at(p, frac + 0.02))

    def captaciones(p: rend.Periodo, asesor: User, n: int) -> None:
        for i, when in enumerate(spread(p, n)):
            c = Captacion(
                negocio=V if i % 2 else A,
                codigo_inmueble=f"INM-{next(codes)}",
                direccion=f"Cl {30 + i} # {40 + i}-{10 + i}, {ZONAS[i % len(ZONAS)]}",
                modo=ModoCaptacion.RAPIDO,
                estado=EstadoCaptacion.APROBADA,
                enviada_at=when,
                verificado_at=when + timedelta(hours=3 if i % 5 else 30),  # some verified late
                verificado_por_id=u["coordinacion"].id,
                asesor_id=asesor.id,
                created_by_id=asesor.id,
            )
            c.created_at = c.updated_at = when
            db.add(c)

    # ---- weights and goals (from last month on)
    config = {
        "asesor": ({"ventas": 50, "captacion": 50}, {"ventas": 1, "captacion": 16}),
        "bruno": ({"captacion": 100}, {"captacion": 20}),
        "carla": ({"arriendos": 100}, {"arriendos": 3}),
        "diego": ({"ventas": 50, "arriendos": 50}, {"ventas": 2, "arriendos": 4}),
    }
    for k, (pesos, metas) in config.items():
        if set(pesos) != set(rend.area_keys(u[k])):
            continue  # someone changed their activities: keep the defaults
        db.add(
            RendimientoConfig(
                user_id=u[k].id,
                periodo=prev.first,
                pesos=pesos,
                metas=metas,
                updated_by_id=u["coordinacion"].id,
            )
        )
    for k in ("atencion", "preventas"):
        db.add(
            RendimientoConfig(
                user_id=u[k].id,
                periodo=prev.first,
                pesos=dict(rend.PESOS_ATENCION),
                metas={
                    a: d.meta_default
                    for a in rend.AREAS_ATENCION
                    if (d := rend.AREAS[a]).meta_default
                },
                updated_by_id=u["gerencia"].id,
            )
        )

    # ---- this month: deals (lead ganado + the asesor's realized visit)
    at_, pv = u["atencion"], u["preventas"]
    ganado(cur, 0.20, V, u["asesor"], at_)
    ganado(cur, 0.30, A, u["carla"], at_)
    ganado(cur, 0.45, A, u["diego"], at_)
    ganado(cur, 0.35, V, u["diego"], pv)
    ganado(cur, 0.55, A, u["diego"], pv)
    ganado(cur, 0.60, V, u["diego"], None)
    ganado(cur, 0.70, A, u["diego"], None)

    # ---- this month: approved captaciones
    captaciones(cur, u["asesor"], 8)
    captaciones(cur, u["bruno"], 15)

    # ---- this month: Atención y Preventa's daily work
    for who, n_leads, n_citas, n_segs, late, perdidos in (
        (
            at_,
            18,
            5,
            18,
            2,
            [
                MotivoPerdida.NUMERO_EQUIVOCADO,
                MotivoPerdida.NUMERO_EQUIVOCADO,
                MotivoPerdida.NO_INTERESADO,
            ],
        ),
        (pv, 14, 6, 8, 1, [MotivoPerdida.PRESUPUESTO]),
    ):
        open_leads = []
        for i, when in enumerate(spread(cur, n_leads)):
            ld = lead(when, V if i % 3 == 0 else A, who)
            llamadas(ld, who, when, 2 if i % 2 else 1)
            open_leads.append(ld)
        for i, ld in enumerate(open_leads[:n_citas]):
            frac = 0.1 + 0.7 * i / max(n_citas - 1, 1)
            asesor = u["diego"] if ld.negocio == V else u["carla"]
            cita(ld, asesor, who, at(cur, frac), at(cur, frac + 0.02))
        for i, when in enumerate(spread(cur, n_segs, 0.05, 0.9)):
            ld = open_leads[i % len(open_leads)]
            s = Seguimiento(
                lead_id=ld.id,
                accion=AccionSeguimiento.LLAMAR,
                due_at=when,
                nota="Volver a llamar",
                created_by_id=who.id,
                done_at=when + (timedelta(hours=4) if i < late else timedelta(minutes=10)),
                done_by_id=who.id,
                resultado="Llamada hecha",
            )
            s.created_at = when - timedelta(days=1)
            db.add(s)
        for i, motivo in enumerate(perdidos):
            frac = 0.15 + 0.55 * i / max(len(perdidos) - 1, 1)
            when = at(cur, frac)
            descuenta = motivo != MotivoPerdida.NUMERO_EQUIVOCADO
            ld = lead(
                when,
                A,
                who,
                EtapaLead.PERDIDO,
                cierre=at(cur, frac + 0.03),
                motivo_perdida=motivo,
                perdida_descuenta=descuenta,
            )
            llamadas(ld, who, when, 3, contesta=motivo != MotivoPerdida.NUMERO_EQUIVOCADO)

    # ---- last month (for «vs el mes anterior»)
    ganado(prev, 0.3, A, u["carla"], at_)
    ganado(prev, 0.4, V, u["diego"], pv)
    ganado(prev, 0.6, A, u["diego"], at_)
    ganado(prev, 0.7, A, u["diego"], None)
    ganado(prev, 0.5, V, u["asesor"], at_)
    ganado(prev, 0.8, A, u["carla"], at_)
    captaciones(prev, u["asesor"], 6)
    captaciones(prev, u["bruno"], 13)
    for who, n in ((at_, 22), (pv, 5)):
        for i in range(n):
            frac = 0.05 + 0.85 * i / max(n - 1, 1)
            when = at(prev, frac)
            ld = lead(
                when,
                A,
                who,
                EtapaLead.PERDIDO,
                cierre=at(prev, frac + 0.04),
                motivo_perdida=MotivoPerdida.NO_CONTESTA,
                perdida_descuenta=False,
            )
            llamadas(ld, who, when, 3 if i % 2 else 2, contesta=False)
            if i < (9 if who is at_ else 3):  # a visit happened before the client stopped answering
                cita(ld, u["carla"], who, when, at(prev, frac + 0.02))

    # ---- ratings (1 to 5): Coordinación rates asesores and Atención; Gerencia the Coordinador
    notas = {
        "asesor": {
            "actitud": 4,
            "puesto": 4,
            "uniforme": 4,
            "material": 4,
            "carne": 5,
            "bateria": 3,
        },
        "bruno": {
            "actitud": 5,
            "puesto": 4,
            "uniforme": 5,
            "material": 4,
            "carne": 5,
            "bateria": 4,
        },
        "carla": {
            "actitud": 4,
            "puesto": 2,
            "uniforme": 4,
            "material": 3,
            "carne": 5,
            "bateria": 4,
        },
        "diego": {
            "actitud": 4,
            "puesto": 4,
            "uniforme": 4,
            "material": 4,
            "carne": 5,
            "bateria": 2,
        },
        "atencion": {"actitud": 5, "puesto": 5, "uniforme": 4, "carne": 5, "bateria": 2},
        "preventas": {"actitud": 4, "puesto": 4, "uniforme": 4, "carne": 4, "bateria": 4},
        "coordinacion": {"actitud": 5, "puesto": 4, "uniforme": 5, "carne": 5, "bateria": 4},
    }
    for p, first_day in ((prev, prev.first), (cur, cur.first)):
        for k, vals in notas.items():
            validos = {i.key for i in rend.indicadores_de(u[k])}
            rater = u["gerencia"] if k == "coordinacion" else u["coordinacion"]
            for ind, v in vals.items():
                if ind not in validos:
                    continue
                c = Calificacion(
                    user_id=u[k].id,
                    periodo=first_day,
                    indicador=ind,
                    valor=min(5, v + 1) if p is prev and v <= 2 else v,
                    calificado_por_id=rater.id,
                )
                c.updated_at = at(p, 0.1)
                db.add(c)

    db.flush()
    return created
