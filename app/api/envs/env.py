"""
Configuración centralizada de variables de entorno usando Pydantic.
Este módulo proporciona validación de tipos y valores por defecto para todas las variables de entorno.
"""

from pydantic import Field, field_validator, ConfigDict

try:
    from pydantic_settings import BaseSettings
except ImportError:
    # Fallback para compatibilidad
    from pydantic import BaseSettings


class Settings(BaseSettings):
    """
    Configuración de la aplicación con validación de tipos usando Pydantic.

    Las variables de entorno se cargan automáticamente y se validan según los tipos definidos.
    """

    model_config = ConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    # Configuración de MongoDB
    mongo_initdb_root_username: str = Field(
        default="root", description="Usuario root de MongoDB"
    )

    mongo_initdb_root_password: str = Field(
        default="root", description="Contraseña root de MongoDB"
    )

    mongo_initdb_database: str = Field(
        default="afapa", description="Nombre de la base de datos MongoDB"
    )

    # Configuración de N8N
    n8n_encryption_key: str = Field(
        description="Clave de encriptación para N8N",
    )

    # Configuración de WAHA
    waha_encryption_key: str = Field(
        description="Clave de encriptación para WAHA",
    )

    waha_api_key: str = Field(
        description="Clave API para WAHA",
    )

    # Configuración adicional de la aplicación
    debug: bool = Field(default=False, description="Modo debug de la aplicación")

    host: str = Field(
        default="0.0.0.0", description="Host donde se ejecutará la aplicación"
    )

    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Puerto donde se ejecutará la aplicación",
    )

    # Configuración de JWT
    jwt_secret_key: str = Field(
        description="Clave secreta para JWT",
    )

    jwt_algorithm: str = Field(default="HS256", description="Algoritmo para JWT")

    jwt_expire_minutes: int = Field(
        default=30, ge=1, description="Tiempo de expiración del JWT en minutos"
    )

    @field_validator("debug")
    @classmethod
    def validate_debug(cls, v):
        """Valida el valor de debug para asegurarse de que sea booleano."""
        if not isinstance(v, bool):
            raise ValueError("El valor de debug debe ser booleano")
        return v

    @field_validator("port")
    @classmethod
    def validate_port(cls, v):
        """Valida el valor de port para asegurarse de que esté en el rango válido."""
        if not (1 <= v <= 65535):
            raise ValueError("El valor de port debe estar entre 1 y 65535")
        if not isinstance(v, int):
            raise ValueError("El valor de port debe ser un entero")
        return v


# Instancia global de configuración
settings = Settings()

# Constantes exportables para importación directa
MONGO_INITDB_ROOT_USERNAME = settings.mongo_initdb_root_username
MONGO_INITDB_ROOT_PASSWORD = settings.mongo_initdb_root_password
MONGO_INITDB_DATABASE = settings.mongo_initdb_database

N8N_ENCRYPTION_KEY = settings.n8n_encryption_key

WAHA_ENCRYPTION_KEY = settings.waha_encryption_key
WAHA_API_KEY = settings.waha_api_key

DEBUG = settings.debug
HOST = settings.host
PORT = settings.port

JWT_SECRET_KEY = settings.jwt_secret_key
JWT_ALGORITHM = settings.jwt_algorithm
JWT_EXPIRE_MINUTES = settings.jwt_expire_minutes
