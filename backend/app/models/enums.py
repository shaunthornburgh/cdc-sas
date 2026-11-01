"""Domain vocabulary agreed with the business.

Rules (enforced in app.services.users, app.api.permissions and the DB):
- Cargo defines the general profile of a person.
- Coordinación turns commercial activities (Captación, Ventas, Arriendos) on/off per person.
- Atención al Cliente and Pre-ventas are separate functions and cannot be combined
  with commercial activities.
- GPS / check-in only applies when Captación is active.
"""

from enum import StrEnum


class Cargo(StrEnum):
    GERENCIA = "gerencia"
    COORDINACION = "coordinacion"
    ASESOR = "asesor"
    AUXILIAR_ADMINISTRATIVA = "auxiliar_administrativa"
    ATENCION_CLIENTE = "atencion_cliente"


class ActividadComercial(StrEnum):
    CAPTACION = "captacion"
    VENTAS = "ventas"
    ARRIENDOS = "arriendos"


class FuncionIndependiente(StrEnum):
    ATENCION_CLIENTE = "atencion_cliente"
    PRE_VENTAS = "pre_ventas"


# ---------------------------------------------------------------- leads y citas
# Prototypes C01 / C02 / C03 and decisions G-013, G-014, G-044, G-045.


class EtapaLead(StrEnum):
    NUEVO = "nuevo"  # llegó, nadie lo sigue o aún sin acciones
    EN_GESTION = "en_gestion"  # contactado / interesado: hay acciones registradas
    SEGUIMIENTO = "seguimiento"  # hay un seguimiento programado pendiente
    CITA_PROGRAMADA = "cita_programada"
    GANADO = "ganado"  # archivado
    PERDIDO = "perdido"  # archivado, con motivo


ETAPAS_CERRADAS = frozenset({EtapaLead.GANADO, EtapaLead.PERDIDO})


class FuenteLead(StrEnum):
    # Plataformas tradicionales
    CIENCUADRAS = "ciencuadras"
    ESPACIO_URBANO = "espacio_urbano"
    PROPPI = "proppi"
    FINCA_RAIZ = "finca_raiz"
    METROCUADRADO = "metrocuadrado"
    # Redes sociales
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    # Otros
    OTRO = "otro"


class TipoNegocio(StrEnum):
    ARRIENDO = "arriendo"
    VENTA = "venta"


class MotivoPerdida(StrEnum):
    NO_CONTESTA = "no_contesta"
    NUMERO_EQUIVOCADO = "numero_equivocado"
    NO_INTERESADO = "no_interesado"
    COMPRO_CON_OTRO = "compro_con_otro"
    PRESUPUESTO = "presupuesto"


class TipoEventoLead(StrEnum):
    RECIBIDO = "recibido"
    SEGUIR = "seguir"
    ASIGNACION = "asignacion"
    LLAMADA = "llamada"
    MENSAJE = "mensaje"
    OPCIONES = "opciones"
    SEGUIMIENTO = "seguimiento"
    OBSERVACION = "observacion"
    CITA = "cita"
    ETAPA = "etapa"
    DATOS = "datos"


class ResultadoLlamada(StrEnum):
    CONTESTO = "contesto"
    NO_CONTESTO = "no_contesto"
    NUMERO_EQUIVOCADO = "numero_equivocado"


class MedioContacto(StrEnum):
    WHATSAPP = "whatsapp"
    CORREO = "correo"
    SMS = "sms"


class AccionSeguimiento(StrEnum):
    LLAMAR = "llamar"
    ENVIAR_OPCIONES = "enviar_opciones"
    ENVIAR_INFORMACION = "enviar_informacion"
    CONFIRMAR_CITA = "confirmar_cita"
    SEGUIMIENTO_PROPUESTA = "seguimiento_propuesta"
    VOLVER_A_CONTACTAR = "volver_a_contactar"


class TipoCita(StrEnum):
    VISITA_ARRIENDO = "visita_arriendo"
    VISITA_VENTA = "visita_venta"
    CAPTACION = "captacion"
    VISITA_CONTROL = "visita_control"
    INVENTARIO = "inventario"
    REUNION_ASESORIA = "reunion_asesoria"


class EstadoCita(StrEnum):
    PENDIENTE = "pendiente"  # pendiente de aceptación por el asesor
    ACEPTADA = "aceptada"
    RECHAZADA = "rechazada"
    REALIZADA = "realizada"
    CANCELADA = "cancelada"


CITA_ACTIVA = frozenset({EstadoCita.PENDIENTE, EstadoCita.ACEPTADA, EstadoCita.RECHAZADA})


# ---------------------------------------------------------------- captaciones
# Prototypes K12 (verificar) / M15 (nueva captación) and decision «Captaciones · registro
# rápido y verificación».


class EstadoCaptacion(StrEnum):
    POR_VERIFICAR = "por_verificar"
    APROBADA = "aprobada"  # suma en Captación y en el rendimiento
    RECHAZADA = "rechazada"  # no cuenta; el asesor la corrige y la vuelve a enviar


class ModoCaptacion(StrEnum):
    RAPIDO = "rapido"  # tipo de negocio, código y dirección
    COMPLETO = "completo"  # todos los datos del inmueble y del propietario


class TipoInmueble(StrEnum):
    APARTAMENTO = "apartamento"
    CASA = "casa"
    LOCAL = "local"
    OFICINA = "oficina"
    LOTE = "lote"
    BODEGA = "bodega"


class MotivoRechazoCaptacion(StrEnum):
    CODIGO_INEXISTENTE = "codigo_inexistente"
    CODIGO_NO_CORRESPONDE = "codigo_no_corresponde"  # a esa dirección


class TipoEventoCaptacion(StrEnum):
    ENVIADA = "enviada"
    EDITADA = "editada"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"
    REENVIADA = "reenviada"
    PUBLICADA = "publicada"
    REASIGNADA = "reasignada"


# ---------------------------------------------------------------- preoperacional
# Prototypes M07 / C08 / K09 and decisions G-007, G-008, G-012 («Preoperacional según medio
# de transporte», «para todos los cargos»).


class MedioTransporte(StrEnum):
    CARRO = "carro"
    MOTO = "moto"
    BICICLETA = "bicicleta"
    TRANSPORTE_PUBLICO = "transporte_publico"
    A_PIE = "a_pie"
    OTRO = "otro"


MEDIOS_CON_VEHICULO = frozenset({MedioTransporte.CARRO, MedioTransporte.MOTO})


# ---------------------------------------------------------------- pedidos
# Prototypes K06 / M06 / C10 and decisions G-006, G-0xx («Pedidos: filtros…», «Pedido vencido»).


class EstadoPedido(StrEnum):
    ABIERTO = "abierto"  # «vencido» is derived: abierto and past its deadline
    ATENDIDO = "atendido"
    PERDIDO = "perdido"


class UrgenciaPedido(StrEnum):
    NORMAL = "normal"
    ALTA = "alta"
    URGENTE = "urgente"


class MotivoPerdidaPedido(StrEnum):
    NO_INTERESARON = "no_interesaron"
    COMPRO_CON_OTRO = "compro_con_otro"
    PRESUPUESTO = "presupuesto"
    NO_RESPONDE = "no_responde"
    OTRO = "otro"


class TipoEventoPedido(StrEnum):
    CREADO = "creado"
    ACTUALIZADO = "actualizado"
    EXTENDIDO = "extendido"
    ATENDIDO = "atendido"
    PERDIDO = "perdido"
    PROPUESTA = "propuesta"
    COMENTARIO = "comentario"
    REASIGNADO = "reasignado"


# ---------------------------------------------------------------- compensación


class EstadoCompensacion(StrEnum):
    """Comisiones y bonos: visto bueno (Auxiliar) → aprobación (Gerencia) → pago (Gerencia)."""

    GENERADA = "generada"
    VISTO_BUENO = "visto_bueno"
    PENDIENTE_PAGO = "pendiente_pago"
    PAGADA = "pagada"
    ANULADA = "anulada"  # negocio caído or a mistake; keeps its history


class TipoComision(StrEnum):
    CERRADOR = "cerrador"  # asesor of the last realized visit
    CAPTADOR = "captador"  # asesor who got the property
    FILTRO = "filtro"  # Atención y Preventa: their cita ended in a deal
    GRUPAL = "grupal"  # Coordinador: the team reached its monthly profit goal
    MANUAL = "manual"


class TipoBono(StrEnum):
    RENDIMIENTO = "rendimiento"
    MANUAL = "manual"


class EstadoCierre(StrEnum):
    CERRADO = "cerrado"
    CAIDO = "caido"  # the lead stopped being «Ganado»


class TipoPago(StrEnum):
    COMISION = "comision"
    BONO = "bono"
    SALARIO = "salario"


class EstadoPago(StrEnum):
    EN_PROCESO = "en_proceso"  # approved, waiting for the transfer
    PAGADO = "pagado"


class EstadoSalario(StrEnum):
    POR_CONFIRMAR = "por_confirmar"
    CONFIRMADO = "confirmado"  # by the Auxiliar
    PAGADO = "pagado"  # Gerencia approved and paid


# ---------------------------------------------------------------- inmuebles


class EstadoInmueble(StrEnum):
    DISPONIBLE = "disponible"  # can be offered to clients
    SEPARADO = "separado"  # a client reserved it; not offered while it lasts
    ARRENDADO = "arrendado"
    VENDIDO = "vendido"
    RETIRADO = "retirado"  # the owner withdrew it, or it's no longer handled


# ---------------------------------------------------------------- administración de inmuebles
# Prototype X14: move-in / move-out inventories, repairs, and owner / tenant requests.


class TipoInventario(StrEnum):
    ENTREGA = "entrega"  # handing the property to the tenant
    RECEPCION = "recepcion"  # getting it back when the contract ends


class EstadoInventario(StrEnum):
    PROGRAMADO = "programado"
    REALIZADO = "realizado"  # the asesor checked the rooms; signatures missing
    CON_NOVEDADES = "con_novedades"  # signed, with damage or missing items
    FIRMADO = "firmado"  # signed, everything fine


class EstadoAmbiente(StrEnum):
    BUENO = "bueno"
    REGULAR = "regular"
    MALO = "malo"


class CategoriaReparacion(StrEnum):
    PLOMERIA = "plomeria"
    ELECTRICO = "electrico"
    HUMEDAD = "humedad"
    CERRAJERIA = "cerrajeria"
    PINTURA = "pintura"
    ELECTRODOMESTICOS = "electrodomesticos"
    OTRO = "otro"


class Prioridad(StrEnum):
    NORMAL = "normal"
    URGENTE = "urgente"


class EstadoReparacion(StrEnum):
    RECIBIDA = "recibida"
    COTIZADA = "cotizada"
    APROBADA = "aprobada"  # by the owner when they pay
    EN_EJECUCION = "en_ejecucion"
    TERMINADA = "terminada"


class PagaReparacion(StrEnum):
    POR_DEFINIR = "por_definir"
    PROPIETARIO = "propietario"
    INQUILINO = "inquilino"
    EMPRESA = "empresa"
    ASEGURADORA = "aseguradora"


class TipoSolicitud(StrEnum):
    PETICION = "peticion"
    QUEJA = "queja"
    RECLAMO = "reclamo"
    SUGERENCIA = "sugerencia"


class Solicitante(StrEnum):
    PROPIETARIO = "propietario"
    INQUILINO = "inquilino"


class CanalSolicitud(StrEnum):
    WHATSAPP = "whatsapp"
    LLAMADA = "llamada"
    CORREO = "correo"
    OFICINA = "oficina"


class EstadoSolicitud(StrEnum):
    ABIERTA = "abierta"
    EN_TRAMITE = "en_tramite"
    RESPONDIDA = "respondida"
    CERRADA = "cerrada"


# ---------------------------------------------------------------- novedades (ausencias y permisos)
# Prototype K13: absences and permits per employee, discounted in «Salarios del mes».


class TipoNovedad(StrEnum):
    INCAPACIDAD = "incapacidad"  # discounted
    PERMISO_NO_REMUNERADO = "permiso_no_remunerado"  # discounted
    PERMISO_REMUNERADO = "permiso_remunerado"  # only counted


NOVEDADES_DESCONTABLES = frozenset({TipoNovedad.INCAPACIDAD, TipoNovedad.PERMISO_NO_REMUNERADO})


class EstadoNovedad(StrEnum):
    REGISTRADA = "registrada"  # Gerencia was notified; counts and discounts
    ANULADA = "anulada"  # a mistake; kept for the record, doesn't count


# ---------------------------------------------------------------- movimientos y GPS
# Prototypes K05 / K05-ger «Movimientos y GPS», M05 «Justificar», K16 / C09 «Trabajo en campo»
# and decisions G-002, G-036, G-039, G-081.


class TipoMovimiento(StrEnum):
    # Alerts: the person justifies them and someone reviews them.
    SALIDA_RUTA = "salida_ruta"  # asesor with Captación left the assigned route
    TIEMPO_DETENIDO = "tiempo_detenido"  # more than N minutes in the same position
    SALIDA_ZONA = "salida_zona"  # Coordinador left the zone of their field activity
    # Field records: no justification; they show who was in the field and for how long.
    TRABAJO_CAMPO = "trabajo_campo"  # Coordinador
    ATENCION_CAMPO = "atencion_campo"  # Atención y Preventa


ALERTAS_GPS = frozenset(
    {TipoMovimiento.SALIDA_RUTA, TipoMovimiento.TIEMPO_DETENIDO, TipoMovimiento.SALIDA_ZONA}
)


class EstadoMovimiento(StrEnum):
    SIN_JUSTIFICAR = "sin_justificar"  # alert waiting for the person («vencida» is derived)
    POR_REVISAR = "por_revisar"  # justified, waiting for Coordinación / Gerencia
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"  # −1 point in rendimiento
    REGISTRO = "registro"  # a field record (trabajo / atención en campo), not an alert


class MotivoMovimiento(StrEnum):
    CITA_FUERA_RUTA = "cita_fuera_ruta"  # salida de ruta / de la zona
    PERMISO_PERSONAL = "permiso_personal"  # salida de ruta / de la zona
    CITA_NO_PROGRAMADA = "cita_no_programada"  # tiempo detenido
    INVENTARIO = "inventario"  # tiempo detenido
    IMPREVISTO_PERSONAL = "imprevisto_personal"  # tiempo detenido


class TipoCampo(StrEnum):
    APOYO_CITA = "apoyo_cita"
    ACOMPANAMIENTO_RUTA = "acompanamiento_ruta"  # Coordinador only
    SALIDA_GRUPAL = "salida_grupal"  # Coordinador only
    OTRA = "otra"


class ActividadCampo(StrEnum):
    CAPTACION = "captacion"
    VISITA_PROPIETARIO = "visita_propietario"
    CITA_VENTA = "cita_venta"
    CITA_ARRIENDO = "cita_arriendo"
    INVENTARIO = "inventario"
    OTRA = "otra"


class TipoEventoMovimiento(StrEnum):
    CREADO = "creado"  # alert reported by the GPS, or field work started
    JUSTIFICADO = "justificado"
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"
    FINALIZADO = "finalizado"  # field work ended
    UBICACION = "ubicacion"  # someone opened the location (privacy log)
    CONFIG = "config"  # alert time / deadline changed (movimiento_id is NULL)
    DESCARGA = "descarga"  # export downloaded (movimiento_id is NULL)


# ---------------------------------------------------------------- plataformas tradicionales
# Prototypes K15 / K15-ger «Actualización de plataformas» and decisions G-0xx (rendimiento del
# Coordinador), G-079 (herramienta de Gerencia).

PLATAFORMAS_TRADICIONALES = (
    FuenteLead.CIENCUADRAS,
    FuenteLead.ESPACIO_URBANO,
    FuenteLead.PROPPI,
    FuenteLead.FINCA_RAIZ,
    FuenteLead.METROCUADRADO,
)


class TipoEventoPlataforma(StrEnum):
    RESPONSABLE = "responsable"  # Gerencia assigned who keeps it updated
    PLAN = "plan"  # a plan was registered or corrected
    ACTIVA = "activa"  # the platform was switched on / off
    REGLA = "regla"  # «se debe actualizar cada N días» changed (plataforma_id is NULL)
    DESCARGA = "descarga"  # history downloaded (plataforma_id is NULL)
