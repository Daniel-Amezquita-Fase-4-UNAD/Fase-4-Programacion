"""
================================================================================
  SOFTWARE FJ - Sistema Integral de Gestión de Clientes, Servicios y Reservas
================================================================================
  Arquitectura: Orientada a Objetos (OOP)
  Principios:   Abstracción, Herencia, Polimorfismo, Encapsulación
  Persistencia: Sin base de datos (listas en memoria + archivo de logs)
================================================================================
"""

from __future__ import annotations
import abc
import uuid
import re
import logging
import traceback
from datetime import datetime, date
from typing import Optional, List
from enum import Enum, auto


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DEL SISTEMA DE LOGS
# ─────────────────────────────────────────────────────────────────────────────

LOG_FILE = "software_fj_eventos.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("SoftwareFJ")


# ─────────────────────────────────────────────────────────────────────────────
# EXCEPCIONES PERSONALIZADAS
# ─────────────────────────────────────────────────────────────────────────────

class SoftwareFJError(Exception):
    """Excepción base del sistema Software FJ."""
    def __init__(self, mensaje: str, codigo: str = "ERR_GENERAL"):
        super().__init__(mensaje)
        self.codigo = codigo
        self.timestamp = datetime.now()

    def __str__(self):
        return f"[{self.codigo}] {super().__str__()} ({self.timestamp.strftime('%H:%M:%S')})"


class ClienteInvalidoError(SoftwareFJError):
    def __init__(self, campo: str, valor):
        super().__init__(
            f"Dato inválido para '{campo}': {repr(valor)}",
            "ERR_CLIENTE"
        )
        self.campo = campo
        self.valor = valor


class ServicioNoDisponibleError(SoftwareFJError):
    def __init__(self, nombre_servicio: str):
        super().__init__(
            f"El servicio '{nombre_servicio}' no está disponible actualmente.",
            "ERR_SERVICIO"
        )


class ReservaInvalidaError(SoftwareFJError):
    def __init__(self, motivo: str):
        super().__init__(motivo, "ERR_RESERVA")


class DuracionInvalidaError(SoftwareFJError):
    def __init__(self, duracion, minimo: int = 1, maximo: int = 480):
        super().__init__(
            f"Duración '{duracion}' fuera del rango permitido ({minimo}-{maximo} min).",
            "ERR_DURACION"
        )


class OperacionNoPermitidaError(SoftwareFJError):
    def __init__(self, operacion: str, estado_actual: str):
        super().__init__(
            f"Operación '{operacion}' no permitida en estado '{estado_actual}'.",
            "ERR_OPERACION"
        )


class ParametroFaltanteError(SoftwareFJError):
    def __init__(self, parametro: str):
        super().__init__(
            f"Parámetro obligatorio faltante: '{parametro}'",
            "ERR_PARAMETRO"
        )


class CalculoInconsistenteError(SoftwareFJError):
    def __init__(self, detalle: str):
        super().__init__(detalle, "ERR_CALCULO")


# ─────────────────────────────────────────────────────────────────────────────
# ENUMERACIONES
# ─────────────────────────────────────────────────────────────────────────────

class EstadoReserva(Enum):
    PENDIENTE   = auto()
    CONFIRMADA  = auto()
    CANCELADA   = auto()
    COMPLETADA  = auto()


class TipoDocumento(Enum):
    CC  = "Cédula de Ciudadanía"
    CE  = "Cédula de Extranjería"
    NIT = "NIT"
    PP  = "Pasaporte"


# ─────────────────────────────────────────────────────────────────────────────
# CLASE ABSTRACTA BASE — EntidadSistema
# ─────────────────────────────────────────────────────────────────────────────

class EntidadSistema(abc.ABC):
    """Clase abstracta raíz del sistema. Toda entidad posee un ID único."""

    def __init__(self):
        self._id: str = str(uuid.uuid4())[:8].upper()
        self._fecha_creacion: datetime = datetime.now()

    @property
    def id(self) -> str:
        return self._id

    @property
    def fecha_creacion(self) -> datetime:
        return self._fecha_creacion

    @abc.abstractmethod
    def descripcion(self) -> str:
        """Retorna una descripción legible de la entidad."""
        ...

    @abc.abstractmethod
    def validar(self) -> bool:
        """Valida que la entidad esté en un estado coherente."""
        ...

    def __repr__(self):
        return f"<{self.__class__.__name__} id={self._id}>"


# ─────────────────────────────────────────────────────────────────────────────
# CLASE Cliente
# ─────────────────────────────────────────────────────────────────────────────

class Cliente(EntidadSistema):
    """
    Representa un cliente de Software FJ.
    Encapsula datos personales con validaciones estrictas.
    """

    _EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}$")
    _TEL_RE   = re.compile(r"^\+?[\d\s\-]{7,15}$")

    def __init__(
        self,
        nombre: str,
        apellido: str,
        email: str,
        telefono: str,
        tipo_doc: TipoDocumento,
        num_doc: str,
    ):
        super().__init__()
        # Usamos setters para disparar validaciones
        self.nombre    = nombre
        self.apellido  = apellido
        self.email     = email
        self.telefono  = telefono
        self._tipo_doc = tipo_doc
        self.num_doc   = num_doc
        self._reservas: List[str] = []   # IDs de reservas del cliente
        logger.info("Cliente creado: %s %s <%s>", self._nombre, self._apellido, self._email)

    # ── Propiedades con validación ──────────────────────────────────────────

    @property
    def nombre(self) -> str:
        return self._nombre

    @nombre.setter
    def nombre(self, valor: str):
        if not isinstance(valor, str) or not valor.strip():
            raise ClienteInvalidoError("nombre", valor)
        self._nombre = valor.strip().title()

    @property
    def apellido(self) -> str:
        return self._apellido

    @apellido.setter
    def apellido(self, valor: str):
        if not isinstance(valor, str) or not valor.strip():
            raise ClienteInvalidoError("apellido", valor)
        self._apellido = valor.strip().title()

    @property
    def email(self) -> str:
        return self._email

    @email.setter
    def email(self, valor: str):
        if not isinstance(valor, str) or not self._EMAIL_RE.match(valor):
            raise ClienteInvalidoError("email", valor)
        self._email = valor.lower()

    @property
    def telefono(self) -> str:
        return self._telefono

    @telefono.setter
    def telefono(self, valor: str):
        if not isinstance(valor, str) or not self._TEL_RE.match(valor):
            raise ClienteInvalidoError("telefono", valor)
        self._telefono = valor

    @property
    def num_doc(self) -> str:
        return self._num_doc

    @num_doc.setter
    def num_doc(self, valor: str):
        if not isinstance(valor, str) or not valor.strip():
            raise ClienteInvalidoError("num_doc", valor)
        self._num_doc = valor.strip()

    @property
    def nombre_completo(self) -> str:
        return f"{self._nombre} {self._apellido}"

    @property
    def reservas(self) -> List[str]:
        return list(self._reservas)

    def agregar_reserva_id(self, reserva_id: str):
        self._reservas.append(reserva_id)

    # ── Métodos abstractos implementados ───────────────────────────────────

    def descripcion(self) -> str:
        return (
            f"Cliente [{self._id}]: {self.nombre_completo} | "
            f"{self._tipo_doc.value}: {self._num_doc} | "
            f"Email: {self._email} | Tel: {self._telefono}"
        )

    def validar(self) -> bool:
        return bool(self._nombre and self._apellido and self._email and self._num_doc)

    def __str__(self):
        return self.descripcion()


# ─────────────────────────────────────────────────────────────────────────────
# CLASE ABSTRACTA Servicio
# ─────────────────────────────────────────────────────────────────────────────

class Servicio(EntidadSistema, abc.ABC):
    """
    Clase abstracta que representa cualquier servicio ofrecido por Software FJ.
    Subclases concretas deben implementar calcular_costo() y describir_servicio().
    """

    IVA_DEFAULT = 0.19   # 19 % IVA Colombia

    def __init__(self, nombre: str, precio_base: float, disponible: bool = True):
        super().__init__()
        self.nombre       = nombre
        self.precio_base  = precio_base
        self._disponible  = disponible
        logger.info("Servicio registrado: [%s] %s — $%.2f", self._id, nombre, precio_base)

    # ── Propiedades ─────────────────────────────────────────────────────────

    @property
    def nombre(self) -> str:
        return self._nombre

    @nombre.setter
    def nombre(self, valor: str):
        if not isinstance(valor, str) or not valor.strip():
            raise ParametroFaltanteError("nombre del servicio")
        self._nombre = valor.strip()

    @property
    def precio_base(self) -> float:
        return self._precio_base

    @precio_base.setter
    def precio_base(self, valor: float):
        try:
            valor = float(valor)
        except (TypeError, ValueError) as e:
            raise CalculoInconsistenteError(
                f"precio_base debe ser numérico, recibido: {repr(valor)}"
            ) from e
        if valor < 0:
            raise CalculoInconsistenteError("precio_base no puede ser negativo.")
        self._precio_base = valor

    @property
    def disponible(self) -> bool:
        return self._disponible

    def activar(self):
        self._disponible = True
        logger.info("Servicio activado: %s", self._nombre)

    def desactivar(self):
        self._disponible = False
        logger.warning("Servicio desactivado: %s", self._nombre)

    def verificar_disponibilidad(self):
        if not self._disponible:
            raise ServicioNoDisponibleError(self._nombre)

    # ── Métodos abstractos ──────────────────────────────────────────────────

    @abc.abstractmethod
    def calcular_costo(self, duracion_minutos: int, **kwargs) -> float:
        """Calcula el costo del servicio según la duración y parámetros extras."""
        ...

    @abc.abstractmethod
    def describir_servicio(self) -> str:
        """Retorna la descripción detallada del servicio."""
        ...

    @abc.abstractmethod
    def validar_parametros(self, duracion_minutos: int, **kwargs) -> bool:
        """Valida los parámetros específicos del servicio."""
        ...

    # ── Método con sobrecarga funcional (parámetros opcionales) ─────────────

    def calcular_costo_con_extras(
        self,
        duracion_minutos: int,
        aplicar_iva: bool = True,
        descuento: float = 0.0,
        recargo: float = 0.0,
        **kwargs,
    ) -> dict:
        """
        Versión enriquecida del cálculo de costo.
        Soporta IVA, descuento porcentual y recargo adicional.
        Retorna desglose completo como dict.
        """
        try:
            if not 0 <= descuento <= 1:
                raise CalculoInconsistenteError(
                    f"Descuento debe estar entre 0 y 1, recibido: {descuento}"
                )
            if recargo < 0:
                raise CalculoInconsistenteError("Recargo no puede ser negativo.")

            subtotal   = self.calcular_costo(duracion_minutos, **kwargs)
            desc_valor = subtotal * descuento
            subtotal_d = subtotal - desc_valor
            recargo_v  = subtotal_d * recargo
            subtotal_r = subtotal_d + recargo_v
            iva_valor  = subtotal_r * self.IVA_DEFAULT if aplicar_iva else 0.0
            total      = subtotal_r + iva_valor

            if total < 0:
                raise CalculoInconsistenteError("Total calculado es negativo. Revise parámetros.")

            return {
                "subtotal":    round(subtotal,   2),
                "descuento":   round(desc_valor, 2),
                "recargo":     round(recargo_v,  2),
                "iva":         round(iva_valor,  2),
                "total":       round(total,      2),
            }
        except CalculoInconsistenteError:
            raise
        except Exception as e:
            raise CalculoInconsistenteError(str(e)) from e

    # ── Métodos abstractos de EntidadSistema ────────────────────────────────

    def descripcion(self) -> str:
        return self.describir_servicio()

    def validar(self) -> bool:
        return self._precio_base >= 0 and bool(self._nombre)

    def __str__(self):
        estado = "✔ Disponible" if self._disponible else "✘ No disponible"
        return f"[{self._id}] {self._nombre} — ${self._precio_base:,.2f} | {estado}"


# ─────────────────────────────────────────────────────────────────────────────
# SERVICIOS ESPECIALIZADOS
# ─────────────────────────────────────────────────────────────────────────────

class ReservaSala(Servicio):
    """
    Servicio de reserva de sala de reuniones o conferencias.
    Precio calculado por hora.
    """

    CAPACIDADES_VALIDAS = [6, 10, 20, 50]

    def __init__(
        self,
        nombre: str,
        precio_por_hora: float,
        capacidad_personas: int,
        piso: int = 1,
        disponible: bool = True,
    ):
        super().__init__(nombre, precio_por_hora, disponible)
        self.capacidad = capacidad_personas
        self._piso     = piso

    @property
    def capacidad(self) -> int:
        return self._capacidad

    @capacidad.setter
    def capacidad(self, valor: int):
        try:
            valor = int(valor)
        except (TypeError, ValueError):
            raise ParametroFaltanteError("capacidad_personas (entero)")
        if valor not in self.CAPACIDADES_VALIDAS:
            raise ServicioNoDisponibleError(
                f"Capacidad {valor} no estándar. Valores: {self.CAPACIDADES_VALIDAS}"
            )
        self._capacidad = valor

    def calcular_costo(self, duracion_minutos: int, **kwargs) -> float:
        self.validar_parametros(duracion_minutos)
        horas = duracion_minutos / 60
        return round(self._precio_base * horas, 2)

    def describir_servicio(self) -> str:
        return (
            f"Sala de Reuniones '{self._nombre}' | "
            f"Capacidad: {self._capacidad} personas | Piso {self._piso} | "
            f"Tarifa: ${self._precio_base:,.2f}/hora"
        )

    def validar_parametros(self, duracion_minutos: int, **kwargs) -> bool:
        try:
            duracion_minutos = int(duracion_minutos)
        except (TypeError, ValueError):
            raise DuracionInvalidaError(duracion_minutos)
        if not (30 <= duracion_minutos <= 480):
            raise DuracionInvalidaError(duracion_minutos, 30, 480)
        return True


class AlquilerEquipo(Servicio):
    """
    Servicio de alquiler de equipos tecnológicos.
    Precio calculado por día o fracción.
    """

    TIPOS_EQUIPO = ["laptop", "proyector", "camara", "servidor", "tablet"]

    def __init__(
        self,
        nombre: str,
        precio_por_dia: float,
        tipo_equipo: str,
        serial: str,
        disponible: bool = True,
    ):
        super().__init__(nombre, precio_por_dia, disponible)
        tipo_equipo = tipo_equipo.lower()
        if tipo_equipo not in self.TIPOS_EQUIPO:
            raise ServicioNoDisponibleError(
                f"Tipo de equipo '{tipo_equipo}' desconocido. Opciones: {self.TIPOS_EQUIPO}"
            )
        self._tipo_equipo = tipo_equipo
        if not serial or not serial.strip():
            raise ParametroFaltanteError("serial del equipo")
        self._serial = serial.strip().upper()

    def calcular_costo(self, duracion_minutos: int, **kwargs) -> float:
        self.validar_parametros(duracion_minutos)
        dias = max(1, duracion_minutos // (60 * 8))   # jornadas de 8 horas
        return round(self._precio_base * dias, 2)

    def describir_servicio(self) -> str:
        return (
            f"Alquiler de Equipo '{self._nombre}' [{self._tipo_equipo.upper()}] | "
            f"Serial: {self._serial} | Tarifa: ${self._precio_base:,.2f}/día"
        )

    def validar_parametros(self, duracion_minutos: int, **kwargs) -> bool:
        try:
            duracion_minutos = int(duracion_minutos)
        except (TypeError, ValueError):
            raise DuracionInvalidaError(duracion_minutos)
        if not (60 <= duracion_minutos <= 60 * 24 * 30):
            raise DuracionInvalidaError(duracion_minutos, 60, 60 * 24 * 30)
        return True


class AsesoriaEspecializada(Servicio):
    """
    Servicio de asesoría profesional o técnica.
    Precio calculado por hora con posible recargo por urgencia.
    """

    AREAS = ["tecnologia", "legal", "contable", "marketing", "recursos_humanos"]

    def __init__(
        self,
        nombre: str,
        precio_por_hora: float,
        area: str,
        asesor: str,
        disponible: bool = True,
    ):
        super().__init__(nombre, precio_por_hora, disponible)
        area = area.lower()
        if area not in self.AREAS:
            raise ServicioNoDisponibleError(
                f"Área de asesoría '{area}' no reconocida. Opciones: {self.AREAS}"
            )
        self._area   = area
        if not asesor or not asesor.strip():
            raise ParametroFaltanteError("nombre del asesor")
        self._asesor = asesor.strip().title()

    def calcular_costo(self, duracion_minutos: int, urgente: bool = False, **kwargs) -> float:
        self.validar_parametros(duracion_minutos)
        horas = duracion_minutos / 60
        costo = self._precio_base * horas
        if urgente:
            costo *= 1.30   # recargo del 30 % por urgencia
        return round(costo, 2)

    def describir_servicio(self) -> str:
        return (
            f"Asesoría '{self._nombre}' | Área: {self._area.replace('_', ' ').title()} | "
            f"Asesor: {self._asesor} | Tarifa: ${self._precio_base:,.2f}/hora"
        )

    def validar_parametros(self, duracion_minutos: int, **kwargs) -> bool:
        try:
            duracion_minutos = int(duracion_minutos)
        except (TypeError, ValueError):
            raise DuracionInvalidaError(duracion_minutos)
        if not (60 <= duracion_minutos <= 480):
            raise DuracionInvalidaError(duracion_minutos, 60, 480)
        return True


# ─────────────────────────────────────────────────────────────────────────────
# CLASE Reserva
# ─────────────────────────────────────────────────────────────────────────────

class Reserva(EntidadSistema):
    """
    Integra un Cliente y un Servicio en una reserva concreta.
    Gestiona ciclo de vida: PENDIENTE → CONFIRMADA → COMPLETADA / CANCELADA.
    """

    def __init__(
        self,
        cliente: Cliente,
        servicio: Servicio,
        duracion_minutos: int,
        fecha_reserva: Optional[date] = None,
        notas: str = "",
        **kwargs_servicio,
    ):
        super().__init__()
        if not isinstance(cliente, Cliente):
            raise ReservaInvalidaError("Se requiere un objeto Cliente válido.")
        if not isinstance(servicio, Servicio):
            raise ReservaInvalidaError("Se requiere un objeto Servicio válido.")

        servicio.verificar_disponibilidad()
        servicio.validar_parametros(duracion_minutos, **kwargs_servicio)

        self._cliente           = cliente
        self._servicio          = servicio
        self._duracion          = int(duracion_minutos)
        self._fecha_reserva     = fecha_reserva or date.today()
        self._notas             = notas
        self._kwargs_servicio   = kwargs_servicio
        self._estado            = EstadoReserva.PENDIENTE
        self._desglose_costo    = {}
        self._historial         = [
            (datetime.now(), EstadoReserva.PENDIENTE, "Reserva creada")
        ]

        cliente.agregar_reserva_id(self._id)
        logger.info(
            "Reserva [%s] creada | Cliente: %s | Servicio: %s | %d min",
            self._id, cliente.nombre_completo, servicio.nombre, duracion_minutos,
        )

    # ── Propiedades ─────────────────────────────────────────────────────────

    @property
    def estado(self) -> EstadoReserva:
        return self._estado

    @property
    def cliente(self) -> Cliente:
        return self._cliente

    @property
    def servicio(self) -> Servicio:
        return self._servicio

    @property
    def desglose(self) -> dict:
        return dict(self._desglose_costo)

    @property
    def historial(self):
        return list(self._historial)

    # ── Cambios de estado ───────────────────────────────────────────────────

    def confirmar(
        self,
        aplicar_iva: bool = True,
        descuento: float = 0.0,
        recargo: float = 0.0,
    ) -> dict:
        """Confirma la reserva y calcula el costo definitivo."""
        try:
            if self._estado != EstadoReserva.PENDIENTE:
                raise OperacionNoPermitidaError("confirmar", self._estado.name)

            desglose = self._servicio.calcular_costo_con_extras(
                self._duracion,
                aplicar_iva=aplicar_iva,
                descuento=descuento,
                recargo=recargo,
                **self._kwargs_servicio,
            )
            self._desglose_costo = desglose
            self._estado = EstadoReserva.CONFIRMADA
            self._historial.append(
                (datetime.now(), EstadoReserva.CONFIRMADA, f"Total: ${desglose['total']:,.2f}")
            )
            logger.info(
                "Reserva [%s] CONFIRMADA | Total: $%s",
                self._id, f"{desglose['total']:,.2f}",
            )
            return desglose

        except (OperacionNoPermitidaError, CalculoInconsistenteError, ServicioNoDisponibleError):
            raise
        except Exception as e:
            raise ReservaInvalidaError(f"Error inesperado al confirmar: {e}") from e
        finally:
            logger.debug("Intento de confirmación finalizado para reserva [%s]", self._id)

    def cancelar(self, motivo: str = "Sin motivo especificado"):
        """Cancela la reserva si no ha sido completada."""
        try:
            if self._estado in (EstadoReserva.CANCELADA, EstadoReserva.COMPLETADA):
                raise OperacionNoPermitidaError("cancelar", self._estado.name)
            self._estado = EstadoReserva.CANCELADA
            self._historial.append(
                (datetime.now(), EstadoReserva.CANCELADA, motivo)
            )
            logger.warning("Reserva [%s] CANCELADA | Motivo: %s", self._id, motivo)
        except OperacionNoPermitidaError:
            raise
        except Exception as e:
            raise ReservaInvalidaError(f"Error al cancelar: {e}") from e

    def completar(self):
        """Marca la reserva como completada (servicio prestado)."""
        try:
            if self._estado != EstadoReserva.CONFIRMADA:
                raise OperacionNoPermitidaError("completar", self._estado.name)
            self._estado = EstadoReserva.COMPLETADA
            self._historial.append(
                (datetime.now(), EstadoReserva.COMPLETADA, "Servicio prestado exitosamente")
            )
            logger.info("Reserva [%s] COMPLETADA", self._id)
        except OperacionNoPermitidaError:
            raise
        except Exception as e:
            raise ReservaInvalidaError(f"Error al completar: {e}") from e

    # ── Métodos abstractos implementados ────────────────────────────────────

    def descripcion(self) -> str:
        return (
            f"Reserva [{self._id}] | Estado: {self._estado.name} | "
            f"Cliente: {self._cliente.nombre_completo} | "
            f"Servicio: {self._servicio.nombre} | "
            f"Duración: {self._duracion} min | "
            f"Fecha: {self._fecha_reserva}"
        )

    def validar(self) -> bool:
        return (
            self._cliente.validar()
            and self._servicio.validar()
            and self._duracion > 0
        )

    def __str__(self):
        return self.descripcion()


# ─────────────────────────────────────────────────────────────────────────────
# GESTOR DEL SISTEMA
# ─────────────────────────────────────────────────────────────────────────────

class GestorSoftwareFJ:
    """
    Controlador central del sistema.
    Mantiene en memoria: clientes, servicios y reservas.
    """

    def __init__(self):
        self._clientes:  List[Cliente]  = []
        self._servicios: List[Servicio] = []
        self._reservas:  List[Reserva]  = []
        logger.info("=== Sistema Software FJ iniciado ===")

    # ── Gestión de clientes ─────────────────────────────────────────────────

    def registrar_cliente(self, **kwargs) -> Optional[Cliente]:
        try:
            cliente = Cliente(**kwargs)
            if not cliente.validar():
                raise ClienteInvalidoError("validación general", kwargs)
            self._clientes.append(cliente)
            return cliente
        except ClienteInvalidoError as e:
            logger.error("Error al registrar cliente: %s", e)
            return None
        except Exception as e:
            logger.critical("Error inesperado en registro de cliente: %s\n%s", e, traceback.format_exc())
            return None

    def buscar_cliente(self, id_cliente: str) -> Optional[Cliente]:
        return next((c for c in self._clientes if c.id == id_cliente), None)

    # ── Gestión de servicios ────────────────────────────────────────────────

    def registrar_servicio(self, servicio: Servicio) -> bool:
        try:
            if not isinstance(servicio, Servicio):
                raise ParametroFaltanteError("instancia de Servicio válida")
            if not servicio.validar():
                raise ServicioNoDisponibleError(getattr(servicio, "_nombre", "desconocido"))
            self._servicios.append(servicio)
            logger.info("Servicio agregado al catálogo: %s", servicio.nombre)
            return True
        except (ParametroFaltanteError, ServicioNoDisponibleError) as e:
            logger.error("Error al registrar servicio: %s", e)
            return False
        except Exception as e:
            logger.critical("Error inesperado al registrar servicio: %s", e)
            return False

    def buscar_servicio(self, id_servicio: str) -> Optional[Servicio]:
        return next((s for s in self._servicios if s.id == id_servicio), None)

    # ── Gestión de reservas ─────────────────────────────────────────────────

    def crear_reserva(
        self,
        cliente: Cliente,
        servicio: Servicio,
        duracion_minutos: int,
        **kwargs,
    ) -> Optional[Reserva]:
        try:
            if cliente is None:
                raise ReservaInvalidaError("Cliente no proporcionado o no encontrado.")
            if servicio is None:
                raise ReservaInvalidaError("Servicio no proporcionado o no encontrado.")
            reserva = Reserva(cliente, servicio, duracion_minutos, **kwargs)
            self._reservas.append(reserva)
            return reserva
        except (ReservaInvalidaError, ServicioNoDisponibleError, DuracionInvalidaError) as e:
            logger.error("Error al crear reserva: %s", e)
            return None
        except Exception as e:
            logger.critical("Error inesperado al crear reserva: %s\n%s", e, traceback.format_exc())
            return None

    # ── Reportes ────────────────────────────────────────────────────────────

    def reporte_resumen(self):
        separador = "─" * 70
        print(f"\n{'═'*70}")
        print("  SOFTWARE FJ — REPORTE DE OPERACIONES")
        print(f"{'═'*70}")
        print(f"  Clientes registrados : {len(self._clientes)}")
        print(f"  Servicios registrados: {len(self._servicios)}")
        print(f"  Reservas totales     : {len(self._reservas)}")

        estados = {e: 0 for e in EstadoReserva}
        for r in self._reservas:
            estados[r.estado] += 1
        for estado, cnt in estados.items():
            print(f"    · {estado.name:<12}: {cnt}")

        print(f"\n  {'DETALLE DE RESERVAS':^66}")
        print(f"  {separador}")
        for r in self._reservas:
            print(f"  {r}")
            if r.desglose:
                d = r.desglose
                print(
                    f"    {'Subtotal':>12}: ${d['subtotal']:>10,.2f}   "
                    f"{'Descuento':>10}: ${d['descuento']:>8,.2f}   "
                    f"{'IVA':>5}: ${d['iva']:>8,.2f}   "
                    f"{'TOTAL':>6}: ${d['total']:>10,.2f}"
                )
        print(f"{'═'*70}\n")


# ─────────────────────────────────────────────────────────────────────────────
# SIMULACIÓN DE OPERACIONES (≥ 10 escenarios)
# ─────────────────────────────────────────────────────────────────────────────

def separador(titulo: str):
    print(f"\n{'─'*70}")
    print(f"  OP: {titulo}")
    print(f"{'─'*70}")


def ejecutar_simulacion():
    gestor = GestorSoftwareFJ()

    # ════════════════════════════════════════════════════════════════════════
    # OP-01: Registro de clientes válidos
    # ════════════════════════════════════════════════════════════════════════
    separador("OP-01 — Registrar clientes válidos")
    try:
        c1 = gestor.registrar_cliente(
            nombre="Laura", apellido="Martínez",
            email="laura@softwarefj.com", telefono="3001234567",
            tipo_doc=TipoDocumento.CC, num_doc="1020304050",
        )
        c2 = gestor.registrar_cliente(
            nombre="Carlos", apellido="Pérez",
            email="cperez@empresa.co", telefono="+573109876543",
            tipo_doc=TipoDocumento.CE, num_doc="CE-987654",
        )
        print(f"  ✔ {c1}")
        print(f"  ✔ {c2}")
    except Exception as e:
        logger.error("OP-01 fallida: %s", e)

    # ════════════════════════════════════════════════════════════════════════
    # OP-02: Registro de cliente con email inválido (debe fallar)
    # ════════════════════════════════════════════════════════════════════════
    separador("OP-02 — Cliente con email inválido (error esperado)")
    try:
        c_malo = Cliente(
            nombre="Pedro", apellido="López",
            email="correo-invalido",          # ← email mal formado
            telefono="3001112233",
            tipo_doc=TipoDocumento.CC, num_doc="555666777",
        )
    except ClienteInvalidoError as e:
        print(f"  ✘ ClienteInvalidoError capturada: {e}")

    # ════════════════════════════════════════════════════════════════════════
    # OP-03: Registro de cliente con nombre vacío (debe fallar)
    # ════════════════════════════════════════════════════════════════════════
    separador("OP-03 — Cliente con nombre vacío (error esperado)")
    try:
        c_malo2 = Cliente(
            nombre="   ", apellido="Rodríguez",
            email="r@domain.com", telefono="3002223344",
            tipo_doc=TipoDocumento.PP, num_doc="AB123456",
        )
    except ClienteInvalidoError as e:
        print(f"  ✘ ClienteInvalidoError capturada: {e}")

    # ════════════════════════════════════════════════════════════════════════
    # OP-04: Crear servicios válidos
    # ════════════════════════════════════════════════════════════════════════
    separador("OP-04 — Registrar servicios válidos")
    try:
        sala_a   = ReservaSala("Sala Innovación", precio_por_hora=120_000, capacidad_personas=10, piso=2)
        equipo_p = AlquilerEquipo("Proyector Epson EB-X51", precio_por_dia=80_000, tipo_equipo="proyector", serial="EPS-2024-007")
        asesoria_t = AsesoriaEspecializada("Asesoría Cloud AWS", precio_por_hora=250_000, area="tecnologia", asesor="Dr. Andrés Gómez")

        gestor.registrar_servicio(sala_a)
        gestor.registrar_servicio(equipo_p)
        gestor.registrar_servicio(asesoria_t)

        print(f"  ✔ {sala_a}")
        print(f"  ✔ {equipo_p}")
        print(f"  ✔ {asesoria_t}")
    except Exception as e:
        logger.error("OP-04 fallida: %s", e)

    # ════════════════════════════════════════════════════════════════════════
    # OP-05: Crear servicio con tipo de equipo inválido (debe fallar)
    # ════════════════════════════════════════════════════════════════════════
    separador("OP-05 — Equipo con tipo inválido (error esperado)")
    try:
        equipo_malo = AlquilerEquipo(
            "Dron DJI Mini", precio_por_dia=300_000,
            tipo_equipo="dron",      # ← no está en la lista
            serial="DJI-001",
        )
    except ServicioNoDisponibleError as e:
        print(f"  ✘ ServicioNoDisponibleError: {e}")

    # ════════════════════════════════════════════════════════════════════════
    # OP-06: Reserva exitosa de sala + confirmación con IVA y descuento
    # ════════════════════════════════════════════════════════════════════════
    separador("OP-06 — Reserva de sala (éxito)")
    try:
        r1 = gestor.crear_reserva(c1, sala_a, duracion_minutos=120)
        if r1:
            desglose = r1.confirmar(aplicar_iva=True, descuento=0.10)
            print(f"  ✔ {r1}")
            print(f"     Desglose: {desglose}")
    except Exception as e:
        logger.error("OP-06 fallida: %s", e)

    # ════════════════════════════════════════════════════════════════════════
    # OP-07: Reserva de asesoría urgente + completar
    # ════════════════════════════════════════════════════════════════════════
    separador("OP-07 — Asesoría urgente (éxito)")
    try:
        r2 = gestor.crear_reserva(c2, asesoria_t, duracion_minutos=180, urgente=True)
        if r2:
            desglose = r2.confirmar(aplicar_iva=True, recargo=0.05)
            print(f"  ✔ {r2}")
            print(f"     Desglose: {desglose}")
            r2.completar()
            print(f"     Estado final: {r2.estado.name}")
    except Exception as e:
        logger.error("OP-07 fallida: %s", e)

    # ════════════════════════════════════════════════════════════════════════
    # OP-08: Reserva con duración fuera de rango (debe fallar)
    # ════════════════════════════════════════════════════════════════════════
    separador("OP-08 — Duración inválida para sala (error esperado)")
    try:
        r_mala = Reserva(c1, sala_a, duracion_minutos=10)  # mínimo 30 min
    except DuracionInvalidaError as e:
        print(f"  ✘ DuracionInvalidaError: {e}")

    # ════════════════════════════════════════════════════════════════════════
    # OP-09: Intentar confirmar una reserva ya confirmada (operación no permitida)
    # ════════════════════════════════════════════════════════════════════════
    separador("OP-09 — Doble confirmación (error esperado)")
    try:
        if r1 and r1.estado == EstadoReserva.CONFIRMADA:
            r1.confirmar()      # segundo intento → debe fallar
    except OperacionNoPermitidaError as e:
        print(f"  ✘ OperacionNoPermitidaError: {e}")

    # ════════════════════════════════════════════════════════════════════════
    # OP-10: Cancelar reserva existente
    # ════════════════════════════════════════════════════════════════════════
    separador("OP-10 — Cancelar reserva de sala")
    try:
        r3 = gestor.crear_reserva(c1, sala_a, duracion_minutos=60)
        if r3:
            r3.cancelar("Cliente solicitó reagendamiento")
            print(f"  ✔ {r3}")
    except Exception as e:
        logger.error("OP-10 fallida: %s", e)

    # ════════════════════════════════════════════════════════════════════════
    # OP-11: Servicio desactivado — reserva rechazada
    # ════════════════════════════════════════════════════════════════════════
    separador("OP-11 — Reserva en servicio desactivado (error esperado)")
    try:
        equipo_p.desactivar()
        r_inactivo = gestor.crear_reserva(c2, equipo_p, duracion_minutos=480)
        if r_inactivo is None:
            print("  ✘ Reserva rechazada correctamente (servicio inactivo)")
    except ServicioNoDisponibleError as e:
        print(f"  ✘ ServicioNoDisponibleError: {e}")

    # ════════════════════════════════════════════════════════════════════════
    # OP-12: Cálculo con descuento inválido (encadenamiento de excepciones)
    # ════════════════════════════════════════════════════════════════════════
    separador("OP-12 — Descuento > 100 % (error esperado con encadenamiento)")
    try:
        r4 = gestor.crear_reserva(c1, sala_a, duracion_minutos=90)
        if r4:
            try:
                r4.confirmar(descuento=1.50)   # 150 % → inválido
            except CalculoInconsistenteError as e:
                print(f"  ✘ CalculoInconsistenteError: {e}")
                if e.__cause__:
                    print(f"     Causado por: {e.__cause__}")
    except Exception as e:
        logger.error("OP-12 fallida: %s", e)

    # ════════════════════════════════════════════════════════════════════════
    # REPORTE FINAL
    # ════════════════════════════════════════════════════════════════════════
    gestor.reporte_resumen()
    print(f"\n  Log completo disponible en: {LOG_FILE}\n")


# ─────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ejecutar_simulacion()
