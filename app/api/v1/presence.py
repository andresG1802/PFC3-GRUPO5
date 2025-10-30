"""Endpoints para gestión de presencia de contactos de WhatsApp"""

from fastapi import APIRouter, HTTPException, Query, Path, Depends, status
from typing import Dict, Any, List, Optional
from datetime import datetime

from ...services.waha_client import (
    get_waha_client,
    WAHAClient,
    WAHAConnectionError,
    WAHAAuthenticationError,
    WAHANotFoundError,
    WAHATimeoutError,
)
from ...services.cache import get_cache
from ..models.presence import (
    PresenceInfo,
    PresenceListResponse,
    PresenceUpdateRequest,
    PresenceResponse,
)
from ...utils.logging_config import get_logger
from .auth import get_current_user

# Logger específico para este módulo
logger = get_logger(__name__)

# Crear router
router = APIRouter(tags=["Presence"])


async def get_waha_dependency() -> WAHAClient:
    """Dependencia para obtener cliente WAHA"""
    try:
        return await get_waha_client()
    except Exception as e:
        logger.error(f"Error obteniendo cliente WAHA: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio WAHA no disponible",
        )


@router.get(
    "/contacts",
    response_model=PresenceListResponse,
    summary="Obtener presencia de múltiples contactos",
    description="""
    Obtiene el estado de presencia de múltiples contactos de WhatsApp.
    
    **Estados de presencia:**
    - `online`: Contacto en línea
    - `offline`: Contacto desconectado
    - `typing`: Contacto escribiendo
    - `recording`: Contacto grabando audio
    - `paused`: Contacto pausó la escritura
    """,
    responses={
        200: {"description": "Lista de presencias obtenida exitosamente"},
        503: {"description": "Servicio WAHA no disponible"},
        500: {"description": "Error interno del servidor"},
    },
)
async def get_contacts_presence(
    contact_ids: List[str] = Query(
        ...,
        description="Lista de IDs de contactos (formato: número@c.us)",
        min_items=1,
        max_items=50,
    ),
    waha_client: WAHAClient = Depends(get_waha_dependency),
    current_user: dict = Depends(get_current_user),
) -> PresenceListResponse:
    """
    Obtiene la presencia de múltiples contactos
    """
    try:
        cache = get_cache()
        presences = []

        for contact_id in contact_ids:
            try:
                # Verificar cache primero
                cache_key = f"presence:{contact_id}"
                cached_presence = cache.get(cache_key)

                if cached_presence:
                    presences.append(
                        PresenceInfo(
                            contact_id=contact_id,
                            presence=cached_presence,
                            last_seen=None,
                            cached=True,
                        )
                    )
                    logger.debug(
                        f"Presencia desde cache para {contact_id}: {cached_presence}"
                    )
                else:
                    # Obtener desde WAHA
                    presence_data = await waha_client.get_contact_presence(contact_id)

                    presence_info = PresenceInfo(
                        contact_id=contact_id,
                        presence=presence_data.get("presence", "offline"),
                        last_seen=presence_data.get("last_seen"),
                        cached=False,
                    )
                    presences.append(presence_info)

                    # Guardar en cache por 5 minutos
                    cache.set(cache_key, presence_info.presence, ttl=300)
                    logger.debug(
                        f"Presencia obtenida para {contact_id}: {presence_info.presence}"
                    )

            except Exception as e:
                logger.warning(f"Error obteniendo presencia para {contact_id}: {e}")
                # Agregar presencia por defecto en caso de error
                presences.append(
                    PresenceInfo(
                        contact_id=contact_id,
                        presence="offline",
                        last_seen=None,
                        cached=False,
                    )
                )

        return PresenceListResponse(
            presences=presences,
            total=len(presences),
            timestamp=datetime.now().isoformat(),
        )

    except WAHAConnectionError:
        logger.error("Error de conexión con WAHA obteniendo presencias")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio WAHA no disponible",
        )
    except Exception as e:
        logger.error(f"Error inesperado obteniendo presencias: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor",
        )


@router.get(
    "/contact/{contact_id}",
    response_model=PresenceResponse,
    summary="Obtener presencia de un contacto específico",
    description="Obtiene el estado de presencia actual de un contacto específico.",
    responses={
        200: {"description": "Presencia obtenida exitosamente"},
        404: {"description": "Contacto no encontrado"},
        503: {"description": "Servicio WAHA no disponible"},
        500: {"description": "Error interno del servidor"},
    },
)
async def get_contact_presence(
    contact_id: str = Path(
        ...,
        description="ID del contacto (formato: número@c.us)",
        pattern=r"^[0-9]+@c\.us$",
    ),
    force_refresh: bool = Query(
        False, description="Forzar actualización desde WAHA (ignorar cache)"
    ),
    waha_client: WAHAClient = Depends(get_waha_dependency),
    current_user: dict = Depends(get_current_user),
) -> PresenceResponse:
    """
    Obtiene la presencia de un contacto específico
    """
    try:
        cache = get_cache()
        cache_key = f"presence:{contact_id}"

        # Verificar cache si no se fuerza refresh
        if not force_refresh:
            cached_presence = cache.get(cache_key)
            if cached_presence:
                logger.info(f"Devolviendo presencia desde cache para {contact_id}")
                return PresenceResponse(
                    presence=PresenceInfo(
                        contact_id=contact_id,
                        presence=cached_presence,
                        last_seen=None,
                        cached=True,
                    ),
                    timestamp=datetime.now().isoformat(),
                )

        # Obtener desde WAHA
        logger.info(f"Obteniendo presencia desde WAHA para {contact_id}")
        presence_data = await waha_client.get_contact_presence(contact_id)

        presence_info = PresenceInfo(
            contact_id=contact_id,
            presence=presence_data.get("presence", "offline"),
            last_seen=presence_data.get("last_seen"),
            cached=False,
        )

        # Guardar en cache por 5 minutos
        cache.set(cache_key, presence_info.presence, ttl=300)

        return PresenceResponse(
            presence=presence_info, timestamp=datetime.now().isoformat()
        )

    except WAHANotFoundError:
        logger.warning(f"Contacto no encontrado: {contact_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contacto no encontrado",
        )
    except WAHAConnectionError:
        logger.error(f"Error de conexión con WAHA para contacto: {contact_id}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio WAHA no disponible",
        )
    except Exception as e:
        logger.error(f"Error inesperado obteniendo presencia: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor",
        )


@router.post(
    "/update",
    response_model=PresenceResponse,
    summary="Actualizar mi presencia",
    description="""
    Actualiza el estado de presencia propio en WhatsApp.
    
    **Estados disponibles:**
    - `online`: Aparecer como en línea
    - `offline`: Aparecer como desconectado
    - `typing`: Mostrar que estoy escribiendo (temporal)
    - `recording`: Mostrar que estoy grabando (temporal)
    """,
    responses={
        200: {"description": "Presencia actualizada exitosamente"},
        400: {"description": "Estado de presencia inválido"},
        503: {"description": "Servicio WAHA no disponible"},
        500: {"description": "Error interno del servidor"},
    },
)
async def update_my_presence(
    presence_request: PresenceUpdateRequest,
    waha_client: WAHAClient = Depends(get_waha_dependency),
    current_user: dict = Depends(get_current_user),
) -> PresenceResponse:
    """
    Actualiza mi estado de presencia
    """
    try:
        logger.info(f"Actualizando presencia a: {presence_request.presence}")

        # Actualizar presencia en WAHA
        result = await waha_client.update_presence(presence_request.presence.value)

        # Crear respuesta
        presence_info = PresenceInfo(
            contact_id="me",
            presence=presence_request.presence.value,
            last_seen=None,
            cached=False,
        )

        return PresenceResponse(
            presence=presence_info, timestamp=datetime.now().isoformat()
        )

    except ValueError as e:
        logger.warning(f"Estado de presencia inválido: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Estado de presencia inválido",
        )
    except WAHAConnectionError:
        logger.error("Error de conexión con WAHA actualizando presencia")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio WAHA no disponible",
        )
    except Exception as e:
        logger.error(f"Error inesperado actualizando presencia: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor",
        )


@router.delete(
    "/cache",
    summary="Limpiar cache de presencias",
    description="Limpia el cache de presencias para forzar actualización desde WAHA.",
    responses={
        200: {
            "description": "Cache limpiado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Cache de presencias limpiado exitosamente",
                        "cleared_entries": 15,
                    }
                }
            },
        }
    },
)
async def clear_presence_cache(
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Limpia el cache de presencias
    """
    try:
        cache = get_cache()

        # Buscar y eliminar todas las entradas de presencia
        pattern = "presence:*"
        presence_keys = cache.get_keys_by_pattern(pattern)

        cleared_count = 0
        for key in presence_keys:
            cache.delete(key)
            cleared_count += 1

        logger.info(
            f"Cache de presencias limpiado - {cleared_count} entradas eliminadas"
        )

        return {
            "message": "Cache de presencias limpiado exitosamente",
            "cleared_entries": cleared_count,
        }

    except Exception as e:
        logger.error(f"Error limpiando cache de presencias: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor",
        )
