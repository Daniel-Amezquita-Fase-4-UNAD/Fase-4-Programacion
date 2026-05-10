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
# CLASE ABSTRACTA BASE 
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

    # ── Método con sobrecarga funcional ─────────────

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