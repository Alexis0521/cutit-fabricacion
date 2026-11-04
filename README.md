# CUTIT – Módulo de Fabricación

Arquetipo básico basado en Python 3.11, FastAPI y PostgreSQL 16.

## Alcance

Implementa el flujo básico de registro, validación, inicio, consulta de fórmula, cierre y reintento de sincronización. Incluye listado paginado, detalle, healthcheck y creación desde callback autenticado con API Key.

## Requisitos

- Docker y Docker Compose.
- Un archivo `.env` con los valores requeridos.
- Contratos reales de Materiales, Inventario y Notificaciones para conectar el modo HTTP.

## Ejecución local

1. Copia `.env.example` a `.env`.
2. Completa las variables obligatorias. Para Docker Compose también define `POSTGRES_DB`, `POSTGRES_USER` y `POSTGRES_PASSWORD`.
3. Ejecuta `docker compose up --build`.
4. Consulta la documentación interactiva de FastAPI en `/docs`.

Los puertos y credenciales se configuran mediante variables de entorno; no se deben reutilizar los valores de ejemplo en producción.

## Modo mock

`EXTERNAL_MODE=mock` habilita respuestas locales simplificadas para probar el flujo sin disponer de los servicios externos. El mock no representa los contratos reales ni simula faltantes de inventario.

## Modo HTTP

`EXTERNAL_MODE=http` utiliza las URLs configuradas:

- Materiales: `GET {MATERIALES_BASE_URL}/materiales/{referencia}`. Respuesta esperada: `{"id":"...","formula":{"estado":"APROBADA","version":"...","items":[...]}}`.
- Inventario: `GET {INVENTARIO_BASE_URL}/inventario/{referencia}`. Respuesta esperada: `{"faltantes":[...]}`.
- Descuento: `POST {INVENTARIO_BASE_URL}/inventario`. Envía `fabricacion_id`, `referencia_material`, `formula`, `cantidad` y cabecera `Idempotency-Key`.
- Notificaciones: el cliente de notificaciones es un adaptador mínimo y debe ajustarse al contrato real.

Estas formas son convenciones provisionales del arquetipo porque los documentos OpenAPI no fueron adjuntados durante la generación.

## Autenticación

La API espera un JWT firmado con `JWT_SECRET` y `JWT_ALGORITHM`. El token debe incluir el claim `role` con uno de estos valores:

- `FABRICANTE`
- `GERENTE_FABRICACION`
- `ENCARGADO_ENSAMBLAJE`

La emisión y renovación de tokens corresponde al proveedor central de identidad, fuera del alcance de este módulo.

## Endpoints principales

- `POST /fabricaciones`
- `POST /fabricaciones/{id}/validacion`
- `PATCH /fabricaciones/{id}/inicio`
- `GET /fabricaciones/{id}/formula`
- `POST /fabricaciones/{id}/cierre`
- `POST /fabricaciones/{id}/sincronizacion`
- `GET /fabricaciones?page=1`
- `GET /fabricaciones/{id}`
- `POST /fabricaciones/desde-notificacion` (requiere `X-API-Key`)
- `GET /health`

## Decisiones y limitaciones conocidas

- `No Sincronizado` es un estado de sincronización independiente. Como convención del arquetipo, la orden permanece `En Proceso` hasta que Inventario confirme el descuento; entonces pasa a `Cerrada`.
- El identificador de fabricación se usa como `Idempotency-Key`; Inventario debe soportar esa semántica para evitar descuentos duplicados.
- La cola persistente no está implementada. La consulta de fórmula es asíncrona a nivel HTTP, pero no utiliza un broker ni un worker durable.
- `modo=urgencia` aún no ordena por existencia física de producto terminado: requiere el contrato correspondiente de Inventario.
- El cierre captura fallos de Inventario y marca `No Sincronizado`; el reintento manual vuelve a enviar el descuento. La garantía de no duplicación depende del soporte de idempotencia del servicio externo.
- La integración real debe validarse contra los OpenAPI de los tres servicios.
- El bootstrap crea tablas automáticamente para facilitar la ejecución inicial. En entornos administrados se deben ejecutar migraciones Alembic.
- Los callbacks HTTPS deben terminar en una infraestructura TLS confiable; la API Key es una autenticación básica y debe rotarse.
- Este arquetipo no afirma cumplir 85%/100% de cobertura todavía. Ejecuta `pytest --cov=app --cov-report=term-missing` y amplía las pruebas hasta alcanzar los umbrales requeridos.
