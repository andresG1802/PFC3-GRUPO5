"""
Módulo de configuración de base de datos MongoDB
"""

from .connection import get_database, close_database_connection
from .models import InteractionModel

__all__ = [
    "get_database",
    "close_database_connection", 
    "InteractionModel"
]