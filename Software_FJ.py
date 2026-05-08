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
