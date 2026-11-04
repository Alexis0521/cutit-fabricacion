from enum import Enum


class EstadoFabricacion(str, Enum):
    REGISTRADA = "Registrada"
    VALIDADA = "Validada"
    EN_PROCESO = "En Proceso"
    CERRADA = "Cerrada"


class EstadoSincronizacion(str, Enum):
    PENDIENTE = "Pendiente"
    SINCRONIZADO = "Sincronizado"
    NO_SINCRONIZADO = "No Sincronizado"


class TipoProducto(str, Enum):
    CADENA = "Cadena"
    CUCHILLA = "Cuchilla"
