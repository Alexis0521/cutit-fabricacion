from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4
from app.domain.enums.estados import EstadoFabricacion, EstadoSincronizacion, TipoProducto
from app.core.exceptions import DomainError


@dataclass
class Fabricacion:
    referencia_material: str
    tipo_producto: TipoProducto
    cantidad: int
    observaciones: str | None = None
    id: UUID = field(default_factory=uuid4)
    estado: EstadoFabricacion = EstadoFabricacion.REGISTRADA
    sincronizacion: EstadoSincronizacion = EstadoSincronizacion.PENDIENTE
    formula_version: str | None = None
    formula_snapshot: dict | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    closed_at: datetime | None = None
    sync_attempts: int = 0

    def __post_init__(self):
        if self.cantidad <= 0:
            raise DomainError("La cantidad debe ser mayor que cero", 422)
        if self.observaciones and len(self.observaciones) > 250:
            raise DomainError("Las observaciones no pueden superar 250 caracteres", 422)

    def validar(self):
        if self.estado != EstadoFabricacion.REGISTRADA:
            raise DomainError("Solo se pueden validar órdenes Registradas")
        self.estado = EstadoFabricacion.VALIDADA

    def iniciar(self, formula: dict):
        if self.estado != EstadoFabricacion.VALIDADA:
            raise DomainError("Solo se pueden iniciar órdenes Validadas")
        if not formula or not formula.get("version"):
            raise DomainError("La fórmula está incompleta", 409)
        if formula.get("estado") != "APROBADA":
            raise DomainError("La fórmula ya no está aprobada", 409)
        self.formula_version = str(formula["version"])
        self.formula_snapshot = formula
        self.started_at = datetime.now(timezone.utc)
        self.estado = EstadoFabricacion.EN_PROCESO

    def cerrar(self):
        if self.estado != EstadoFabricacion.EN_PROCESO:
            raise DomainError("Solo se pueden cerrar órdenes En Proceso")
        self.sync_attempts += 1

    def marcar_cerrada(self):
        self.estado = EstadoFabricacion.CERRADA
        self.sincronizacion = EstadoSincronizacion.SINCRONIZADO
        self.closed_at = datetime.now(timezone.utc)

    def marcar_no_sincronizada(self):
        # Archetype Convention Addition: la orden permanece En Proceso hasta confirmar
        # el descuento remoto; el estado de sincronización registra el fallo por separado.
        self.sincronizacion = EstadoSincronizacion.NO_SINCRONIZADO
