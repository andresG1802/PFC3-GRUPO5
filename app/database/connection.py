"""
Configuración de conexión a MongoDB
"""

from pymongo import MongoClient
from pymongo.database import Database
from typing import Optional
import logging
from ..api.envs import (
    MONGO_INITDB_ROOT_USERNAME,
    MONGO_INITDB_ROOT_PASSWORD,
    MONGO_INITDB_DATABASE,
)

# Configurar logging
logger = logging.getLogger(__name__)

# Cliente global de MongoDB
_client: Optional[MongoClient] = None
_database: Optional[Database] = None


def get_mongodb_url() -> str:
    """
    Construye la URL de conexión a MongoDB

    Returns:
        str: URL de conexión a MongoDB
    """
    return f"mongodb://{MONGO_INITDB_ROOT_USERNAME}:{MONGO_INITDB_ROOT_PASSWORD}@localhost:27017/{MONGO_INITDB_DATABASE}?authSource=admin"


def get_database() -> Database:
    """
    Obtiene la instancia de la base de datos MongoDB

    Returns:
        Database: Instancia de la base de datos
    """
    global _client, _database

    if _database is None:
        try:
            mongodb_url = get_mongodb_url()
            _client = MongoClient(mongodb_url)

            # Verificar conexión
            _client.admin.command("ping")
            logger.info("Conexión a MongoDB establecida correctamente")

            _database = _client[MONGO_INITDB_DATABASE]

        except Exception as e:
            logger.error(f"Error al conectar con MongoDB: {e}")
            raise

    return _database


def close_database_connection():
    """
    Cierra la conexión a MongoDB
    """
    global _client, _database

    if _client:
        _client.close()
        _client = None
        _database = None
        logger.info("Conexión a MongoDB cerrada")


# Función para obtener colecciones específicas
def get_interactions_collection():
    """
    Obtiene la colección de interactions

    Returns:
        Collection: Colección de interactions
    """
    db = get_database()
    return db.interactions


def get_asesores_collection():
    """
    Obtiene la colección de asesores

    Returns:
        Collection: Colección de asesores
    """
    db = get_database()
    return db.asesores
