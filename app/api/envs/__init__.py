"""
Módulo de configuración de variables de entorno.
Exporta todas las variables de entorno validadas como constantes.
"""

from .env import (API_PORT, DEBUG, HOST, JWT_ALGORITHM, JWT_EXPIRE_MINUTES,
                  JWT_SECRET_KEY, MONGO_INITDB_DATABASE,
                  MONGO_INITDB_ROOT_PASSWORD, MONGO_INITDB_ROOT_USERNAME,
                  N8N_ENCRYPTION_KEY, WAHA_API_KEY, WAHA_ENCRYPTION_KEY)

__all__ = [
    "MONGO_INITDB_ROOT_USERNAME",
    "MONGO_INITDB_ROOT_PASSWORD",
    "MONGO_INITDB_DATABASE",
    "N8N_ENCRYPTION_KEY",
    "WAHA_ENCRYPTION_KEY",
    "WAHA_API_KEY",
    "DEBUG",
    "HOST",
    "API_PORT",
    "JWT_SECRET_KEY",
    "JWT_ALGORITHM",
    "JWT_EXPIRE_MINUTES",
]
