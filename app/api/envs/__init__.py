"""
Módulo de configuración de variables de entorno.
Exporta todas las variables de entorno validadas como constantes.
"""

from .env import (  # Instancia de configuración; Variables de MongoDB; Variables de N8N; Variables de WAHA; Variables de la aplicación; Variables de JWT
    DEBUG, HOST, JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET_KEY,
    MONGO_INITDB_DATABASE, MONGO_INITDB_ROOT_PASSWORD,
    MONGO_INITDB_ROOT_USERNAME, N8N_ENCRYPTION_KEY, API_PORT, WAHA_API_KEY,
    WAHA_ENCRYPTION_KEY, settings)

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
    "API_PORT",
    # Variables de JWT
    "JWT_SECRET_KEY",
    "JWT_ALGORITHM",
    "JWT_EXPIRE_MINUTES",
]
