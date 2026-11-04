from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    materiales_base_url: str
    inventario_base_url: str
    notificaciones_base_url: str
    external_timeout_seconds: float = 5
    external_mode: str = "mock"
    callback_api_key: str
    api_host: str = "0.0.0.0"
    api_port: int

    @property
    def allowed_roles(self) -> set[str]:
        return {"FABRICANTE", "GERENTE_FABRICACION", "ENCARGADO_ENSAMBLAJE"}


settings = Settings()
