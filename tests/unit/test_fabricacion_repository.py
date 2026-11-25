from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.domain.entities.fabricacion import Fabricacion
from app.domain.enums.estados import EstadoFabricacion, TipoProducto
from app.infrastructure.database.connection import Base
from app.infrastructure.repositories.fabricacion_repository import FabricacionRepository


def test_repository_persists_fabricacion_update_fields():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    try:
        with Session(engine) as session:
            repository = FabricacionRepository(session)
            entity = Fabricacion(
                referencia_material="MAT-1",
                tipo_producto=TipoProducto.CADENA,
                cantidad=3,
                fabricante_id="fab-1",
                especificaciones_tecnicas="Acero inoxidable",
                insumos_terceros=[{"nombre": "Tornillo", "cantidad": 4}],
                estado=EstadoFabricacion.VALIDADA,
            )

            repository.save(entity)
            loaded = repository.get(entity.id)

        assert loaded is not None
        assert loaded.fabricante_id == "fab-1"
        assert loaded.especificaciones_tecnicas == "Acero inoxidable"
        assert loaded.insumos_terceros == [{"nombre": "Tornillo", "cantidad": 4}]
        assert loaded.estado == EstadoFabricacion.VALIDADA
    finally:
        engine.dispose()
