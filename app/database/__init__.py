"""
Módulo de configuración de base de datos MongoDB
"""

from .connection import close_database_connection, get_database
from .models import InteractionModel

__all__ = ["get_database", "close_database_connection", "InteractionModel"]
