"""
Seeder para poblar la base de datos con datos de prueba
"""

import logging
from datetime import datetime, timedelta
from typing import List
from .models import AsesorModel, InteractionModel
from ..api.envs import DEBUG
from ..api.v1.auth import hash_password

# Configurar logging
logger = logging.getLogger(__name__)


def create_test_asesores() -> List[str]:
    """
    Crea asesores de prueba

    Returns:
        List[str]: Lista de IDs de asesores creados
    """
    asesores_data = []

    if DEBUG:
        # Datos de prueba más extensos para desarrollo
        asesores_data = [
            {
                "email": "admin@test.com",
                "password": hash_password("admin123"),
                "full_name": "Administrador de Prueba",
                "role": "admin",
            },
            {
                "email": "asesor1@test.com",
                "password": hash_password("asesor123"),
                "full_name": "Juan Pérez",
                "role": "asesor",
            },
            {
                "email": "asesor2@test.com",
                "password": hash_password("asesor123"),
                "full_name": "María García",
                "role": "asesor",
            },
            {
                "email": "asesor3@test.com",
                "password": hash_password("asesor123"),
                "full_name": "Carlos López",
                "role": "asesor",
            },
        ]
    else:
        # Datos mínimos para producción
        asesores_data = [
            {
                "email": "admin@arulink.com",
                "password": hash_password("admin2024!"),
                "full_name": "Administrador Principal",
                "role": "admin",
            }
        ]

    created_ids = []

    for asesor_data in asesores_data:
        # Verificar si el asesor ya existe
        existing_asesor = AsesorModel.find_by_email(asesor_data["email"])
        if not existing_asesor:
            try:
                asesor_id = AsesorModel.create_asesor(
                    email=asesor_data["email"],
                    password=asesor_data["password"],
                    full_name=asesor_data["full_name"],
                    role=asesor_data["role"],
                )
                created_ids.append(str(asesor_id))
                logger.info(
                    f"Asesor creado: {asesor_data['email']} ({asesor_data['role']})"
                )
            except Exception as e:
                logger.error(f"Error creando asesor {asesor_data['email']}: {e}")
        else:
            logger.info(f"Asesor ya existe: {asesor_data['email']}")
            created_ids.append(str(existing_asesor["_id"]))

    return created_ids


def create_test_interactions(asesor_ids: List[str]) -> List[str]:
    """
    Crea interactions de prueba

    Args:
        asesor_ids: Lista de IDs de asesores para asignar

    Returns:
        List[str]: Lista de IDs de interactions creadas
    """
    if not DEBUG:
        # No crear interactions de prueba en producción
        return []

    interactions_data = [
        {
            "phone": "+59178123456",
            "state": "menus",
            "route": "route_1",
            "step": 1,
            "lang": "es",
            "timeline": [],  # Sin timeline porque está en el primer paso
        },
        {
            "phone": "+59178234567",
            "state": "pending",
            "route": "route_2",
            "step": 3,
            "lang": "qu",
            "timeline": [
                {
                    "route": "route_2",
                    "step": 1,
                    "userInput": "Consulta sobre servicios",
                },
                {"route": "route_2", "step": 2, "userInput": "Más información"},
            ],  # Timeline muestra los pasos ANTERIORES que llevaron al step actual (3)
            "asesor_id": asesor_ids[1] if len(asesor_ids) > 1 else None,
            "assignedAt": datetime.utcnow() - timedelta(hours=2),
        },
        {
            "phone": "+59178345678",
            "state": "derived",
            "route": "route_3",
            "step": 2,
            "lang": "es",
            "timeline": [
                {"route": "route_3", "step": 1, "userInput": "Problema técnico"}
            ],  # Timeline muestra el paso ANTERIOR que llevó al step actual (2)
            "asesor_id": asesor_ids[2] if len(asesor_ids) > 2 else None,
            "assignedAt": datetime.utcnow() - timedelta(hours=1),
        },
        {
            "phone": "+59178456789",
            "state": "closed",
            "route": "route_4",
            "step": 5,
            "lang": "es",
            "timeline": [
                {"route": "route_4", "step": 1, "userInput": "Consulta inicial"},
                {"route": "route_4", "step": 2, "userInput": "Proporcionar detalles"},
                {"route": "route_4", "step": 3, "userInput": "Solicitar solución"},
                {"route": "route_4", "step": 4, "userInput": "Confirmar resolución"},
            ],  # Timeline muestra los pasos ANTERIORES que llevaron al step actual (5)
            "asesor_id": asesor_ids[1] if len(asesor_ids) > 1 else None,
            "assignedAt": datetime.utcnow() - timedelta(days=1),
        },
        {
            "phone": "+59178567890",
            "state": "menus",
            "route": "route_1",
            "step": 2,
            "lang": "qu",
            "timeline": [
                {"route": "route_1", "step": 1, "userInput": "Inicio de conversación"}
            ],  # Timeline muestra el paso ANTERIOR que llevó al step actual (2)
        },
    ]

    created_ids = []

    for interaction_data in interactions_data:
        # Verificar si la interaction ya existe
        existing_interaction = InteractionModel.find_by_phone(interaction_data["phone"])
        if not existing_interaction:
            try:
                interaction_id = InteractionModel.create(interaction_data)
                created_ids.append(interaction_id)
                logger.info(
                    f"Interaction creada: {interaction_data['phone']} (estado: {interaction_data['state']})"
                )
            except Exception as e:
                logger.error(
                    f"Error creando interaction {interaction_data['phone']}: {e}"
                )
        else:
            logger.info(f"Interaction ya existe: {interaction_data['phone']}")
            created_ids.append(str(existing_interaction["_id"]))

    return created_ids


def seed_database():
    """
    Función principal para poblar la base de datos
    """
    logger.info("Iniciando seeding de la base de datos...")

    if DEBUG:
        logger.info("Modo DEBUG activado - Creando datos de prueba extensos")
    else:
        logger.info("Modo PRODUCCIÓN - Creando datos mínimos")

    try:
        # Crear asesores
        asesor_ids = create_test_asesores()
        logger.info(f"Asesores procesados: {len(asesor_ids)}")

        # Crear interactions (solo en modo DEBUG)
        interaction_ids = create_test_interactions(asesor_ids)
        if interaction_ids:
            logger.info(f"Interactions creadas: {len(interaction_ids)}")

        logger.info("Seeding completado exitosamente")

    except Exception as e:
        logger.error(f"Error durante el seeding: {e}")
        raise


def clear_database():
    """
    Función para limpiar la base de datos (solo en modo DEBUG)
    """
    if not DEBUG:
        logger.warning("No se puede limpiar la base de datos en modo producción")
        return

    logger.warning("Limpiando base de datos...")

    try:
        from .connection import get_interactions_collection, get_asesores_collection

        # Limpiar collections
        interactions_collection = get_interactions_collection()
        asesores_collection = get_asesores_collection()

        interactions_deleted = interactions_collection.delete_many({}).deleted_count
        asesores_deleted = asesores_collection.delete_many({}).deleted_count

        logger.info(f"Interactions eliminadas: {interactions_deleted}")
        logger.info(f"Asesores eliminados: {asesores_deleted}")
        logger.info("Base de datos limpiada exitosamente")

    except Exception as e:
        logger.error(f"Error limpiando la base de datos: {e}")
        raise
