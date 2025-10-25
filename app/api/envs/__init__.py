"""
Módulo de configuración de variables de entorno.
Exporta todas las variables de entorno validadas como constantes.
"""

from .env import (
    # Instancia de configuración
    settings,
    # Variables de MongoDB
    MONGO_INITDB_ROOT_USERNAME,
    MONGO_INITDB_ROOT_PASSWORD,
    MONGO_INITDB_DATABASE,
    # Variables de N8N
    N8N_ENCRYPTION_KEY,
    # Variables de WAHA
    WAHA_ENCRYPTION_KEY,
    WAHA_API_KEY,
    # Variables de la aplicación
    DEBUG,
    HOST,
    PORT,
    # Variables de JWT
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    JWT_EXPIRE_MINUTES,
)

__all__ = [
    # Variables de MongoDB
    "MONGO_INITDB_ROOT_USERNAME",
    "MONGO_INITDB_ROOT_PASSWORD",
    "MONGO_INITDB_DATABASE",
    # Variables de N8N
    "N8N_ENCRYPTION_KEY",
    # Variables de WAHA
    "WAHA_ENCRYPTION_KEY",
    "WAHA_API_KEY",
    # Variables de la aplicación
    "DEBUG",
    "HOST",
    "PORT",
    # Variables de JWT
    "JWT_SECRET_KEY",
    "JWT_ALGORITHM",
    "JWT_EXPIRE_MINUTES",
]
