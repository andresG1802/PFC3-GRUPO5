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
    Detecta automáticamente si se ejecuta en Docker o localmente

    Returns:
        str: URL de conexión a MongoDB
    """
    import os

    # Detectar si estamos en un contenedor Docker
    is_docker = os.path.exists("/.dockerenv") or os.environ.get(
        "DOCKER_CONTAINER", False
    )

    if is_docker:
        # Dentro de Docker, usar el nombre del servicio
        host = "db"
        port = "27017"
        logger.info(f"Conectando a MongoDB en Docker: {host}:{port}")
    else:
        # Fuera de Docker, usar localhost con el puerto mapeado
        host = "localhost"
        # Obtener el puerto mapeado desde docker ps o usar el puerto por defecto
        port = "63445"  # Puerto mapeado actual según docker ps
        logger.info(f"Conectando a MongoDB localmente: {host}:{port}")

    return f"mongodb://{MONGO_INITDB_ROOT_USERNAME}:{MONGO_INITDB_ROOT_PASSWORD}@{host}:{port}/{MONGO_INITDB_DATABASE}?authSource=admin"


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
