"""Endpoints para gestión de chats de WhatsApp"""

from fastapi import APIRouter, HTTPException, Query, Path, Depends, status
from typing import List, Dict, Any
from datetime import datetime

from ...services.waha_client import (
    get_waha_client,
    WAHAClient,
    WAHAConnectionError,
    WAHAAuthenticationError,
    WAHANotFoundError,
    WAHATimeoutError,
)
from ...services.cache import (
    get_cache,
    cache_key_for_chats,
    cache_key_for_chat,
    cache_key_for_overview,
)
from ..models.chats import (
    Chat,
    ChatOverview,
    ChatListResponse,
    ChatResponse,
    ErrorResponse,
    ChatFilters,
)
from ...utils.logging_config import get_logger

# Logger específico para este módulo
logger = get_logger(__name__)

# Crear router
router = APIRouter(tags=["Chats"])


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
    "/",
    response_model=ChatListResponse,
    summary="Obtener lista de chats",
    description="Obtiene una lista paginada de chats de WhatsApp desde WAHA API con caché optimizado",
    responses={
        200: {"description": "Lista de chats obtenida exitosamente"},
        503: {"description": "Servicio WAHA no disponible"},
        504: {"description": "Timeout en comunicación con WAHA"},
        500: {"description": "Error interno del servidor"},
    },
)
async def get_chats(
    limit: int = Query(
        20, ge=1, le=100, description="Número máximo de chats a obtener"
    ),
    offset: int = Query(0, ge=0, description="Desplazamiento para paginación"),
    waha_client: WAHAClient = Depends(get_waha_dependency),
) -> ChatListResponse:
    """
    Obtiene todos los chats con paginación
    """
    try:
        # Verificar cache
        cache = get_cache()
        cache_key = cache_key_for_chats(limit, offset)
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(
                f"Devolviendo chats desde cache: limit={limit}, offset={offset}"
            )
            return ChatListResponse(**cached_result)

        logger.info(f"Obteniendo chats - limit: {limit}, offset: {offset}")

        # Obtener chats desde WAHA
        raw_chats = await waha_client.get_chats(limit=limit, offset=offset)

        # Normalizar datos
        normalized_chats = []
        for raw_chat in raw_chats:
            try:
                normalized_data = waha_client._normalize_chat_data(raw_chat)
                chat = Chat(**normalized_data)
                normalized_chats.append(chat)
            except Exception as e:
                logger.warning(
                    f"Error normalizando chat {raw_chat.get('id', 'unknown')}: {e}"
                )
                continue

        # Crear respuesta
        response_data = {
            "chats": normalized_chats,
            "total": len(normalized_chats),
            "limit": limit,
            "offset": offset,
            "has_more": len(normalized_chats) == limit,  # Estimación
            "timestamp": datetime.now().isoformat(),
        }

        # Guardar en cache
        cache.set(cache_key, response_data, ttl=300)  # 5 minutos

        logger.info(f"Devueltos {len(normalized_chats)} chats exitosamente")
        return ChatListResponse(**response_data)

    except WAHAAuthenticationError as e:
        logger.error(f"Error de autenticación WAHA: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autorizado: API Key de WAHA inválida",
        )
    except WAHATimeoutError as e:
        logger.error(f"Timeout WAHA: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout en la comunicación con WAHA",
        )
    except WAHAConnectionError as e:
        logger.error(f"Error de conexión WAHA: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio WAHA no disponible",
        )
    except Exception as e:
        logger.error(f"Error inesperado obteniendo chats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor",
        )


@router.get(
    "/overview",
    summary="Obtener vista general de chats",
    description="""
    Obtiene una vista general optimizada de chats con información básica.
    
    **Características:**
    - Respuesta más rápida que el endpoint completo
    - Solo información esencial de cada chat
    - Ideal para listados y navegación
    - Cache optimizado de 5 minutos
    
    **Parámetros:**
    - `limit`: Número máximo de chats (1-100, por defecto 20)
    - `offset`: Desplazamiento para paginación (por defecto 0)
    
    **Respuesta:**
    ```json
    {
        "success": true,
        "data": {
            "summary": {
                "total_chats": 25,
                "limit": 20,
                "offset": 0
            },
            "chats": [
                {
                    "id": "5491234567890@c.us",
                    "name": "Juan Pérez",
                    "unread_count": 3,
                    "last_message_time": "2024-01-15T10:30:00Z",
                    "is_group": false,
                    "is_archived": false
                }
            ]
        },
        "message": "Overview de chats obtenido exitosamente"
    }
    ```
    """,
    responses={
        200: {
            "description": "Vista general obtenida exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "summary": {"total_chats": 25, "limit": 20, "offset": 0},
                            "chats": [
                                {
                                    "id": "5491234567890@c.us",
                                    "name": "Juan Pérez",
                                    "unread_count": 3,
                                    "last_message_time": "2024-01-15T10:30:00Z",
                                    "is_group": False,
                                    "is_archived": False,
                                }
                            ],
                        },
                        "message": "Overview de chats obtenido exitosamente",
                    }
                }
            },
        },
        503: {"description": "Servicio WAHA no disponible", "model": ErrorResponse},
        504: {
            "description": "Timeout en comunicación con WAHA",
            "model": ErrorResponse,
        },
    },
    tags=["Chats", "Overview"],
)
async def get_chats_overview(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    waha_client: WAHAClient = Depends(get_waha_dependency),
) -> Dict[str, Any]:
    """
    Obtiene vista general de chats optimizada
    """
    try:
        # Verificar cache
        cache = get_cache()
        cache_key = cache_key_for_overview(limit, offset)
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(
                f"Devolviendo overview desde cache: limit={limit}, offset={offset}"
            )
            return {
                "success": True,
                "data": {
                    "summary": {
                        "total_chats": len(cached_result),
                        "limit": limit,
                        "offset": offset,
                    },
                    "chats": cached_result,
                },
                "message": "Overview de chats obtenido desde cache",
            }

        logger.info(f"Obteniendo chats overview - limit: {limit}, offset: {offset}")

        # Intentar obtener overview optimizado, fallback a chats normales
        try:
            raw_chats = await waha_client.get_chats_overview(limit=limit, offset=offset)
        except:
            logger.warning("Overview no disponible, usando chats normales")
            raw_chats = await waha_client.get_chats(limit=limit, offset=offset)

        # Crear objetos ChatOverview
        overview_chats = []
        for raw_chat in raw_chats:
            try:
                # Determinar el tipo de chat
                chat_type = "group" if raw_chat.get("isGroup", False) else "individual"

                overview_data = {
                    "id": raw_chat.get("id", ""),
                    "name": raw_chat.get("name")
                    or raw_chat.get("formattedTitle", "Chat sin nombre"),
                    "type": chat_type,
                    "timestamp": raw_chat.get("timestamp"),
                    "unread_count": raw_chat.get("unreadCount", 0),
                    "archived": raw_chat.get("archived", False),
                    "pinned": raw_chat.get("pinned", False),
                }
                overview_chats.append(ChatOverview(**overview_data))
            except Exception as e:
                logger.warning(
                    f"Error creando overview para chat {raw_chat.get('id', 'unknown')}: {e}"
                )
                continue

        # Guardar en cache
        cache.set(cache_key, [chat.dict() for chat in overview_chats], ttl=300)

        # Crear respuesta estructurada
        response_data = {
            "success": True,
            "data": {
                "summary": {
                    "total_chats": len(overview_chats),
                    "limit": limit,
                    "offset": offset,
                },
                "chats": [chat.dict() for chat in overview_chats],
            },
            "message": "Overview de chats obtenido exitosamente",
        }

        logger.info(f"Devueltos {len(overview_chats)} chats overview exitosamente")
        return response_data

    except Exception as e:
        logger.error(f"Error obteniendo chats overview: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Error obteniendo vista general de chats",
        )


@router.get(
    "/{chat_id}",
    response_model=ChatResponse,
    summary="Obtener chat específico",
    description="""
    Obtiene información detallada de un chat específico por su ID.
    
    **Características:**
    - Información completa del chat
    - Detalles del contacto o grupo
    - Último mensaje si está disponible
    - Cache optimizado de 10 minutos
    
    **Formato del chat_id:**
    - Para contactos individuales: `5491234567890@c.us`
    - Para grupos: `120363123456789012@g.us`
    """,
    responses={
        200: {
            "description": "Chat obtenido exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "id": "5491234567890@c.us",
                            "name": "Juan Pérez",
                            "type": "individual",
                            "contact": {
                                "id": "5491234567890@c.us",
                                "name": "Juan Pérez",
                                "phone": "+5491234567890",
                                "is_business": False,
                            },
                            "last_message": {
                                "id": "msg123",
                                "body": "Hola, ¿cómo estás?",
                                "type": "text",
                                "timestamp": "2024-01-15T10:30:00Z",
                                "from_me": False,
                                "ack": "read",
                            },
                            "unread_count": 2,
                            "is_pinned": False,
                            "is_archived": False,
                            "is_muted": False,
                        },
                        "message": "Chat obtenido exitosamente",
                    }
                }
            },
        },
        404: {
            "description": "Chat no encontrado",
            "content": {
                "application/json": {
                    "example": {
                        "error": "not_found",
                        "message": "Chat no encontrado",
                        "detail": "El chat especificado no existe o no es accesible",
                    }
                }
            },
        },
        503: {"description": "Servicio WAHA no disponible", "model": ErrorResponse},
        504: {
            "description": "Timeout en comunicación con WAHA",
            "model": ErrorResponse,
        },
    },
    tags=["Chats", "Individual"],
)
async def get_chat_by_id(
    chat_id: str = Path(
        ...,
        description="ID único del chat",
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9@._-]+$",
    ),
    waha_client: WAHAClient = Depends(get_waha_dependency),
) -> ChatResponse:
    """
    Obtiene un chat específico por ID
    """
    try:
        # Verificar cache
        cache = get_cache()
        cache_key = cache_key_for_chat(chat_id)
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"Devolviendo chat desde cache: {chat_id}")
            return ChatResponse(**cached_result)

        logger.info(f"Obteniendo chat específico: {chat_id}")

        # Obtener chat desde WAHA
        raw_chat = await waha_client.get_chat_by_id(chat_id)

        if not raw_chat:
            logger.warning(f"Chat no encontrado: {chat_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat con ID '{chat_id}' no encontrado",
            )

        # Normalizar datos
        normalized_data = waha_client._normalize_chat_data(raw_chat)
        chat = Chat(**normalized_data)

        # Crear respuesta
        response_data = {
            "success": True,
            "data": chat.dict(),
            "message": "Chat obtenido exitosamente",
        }

        # Guardar en cache
        cache.set(
            cache_key, response_data, ttl=600
        )  # 10 minutos para chats específicos

        logger.info(f"Chat {chat_id} obtenido exitosamente")
        return ChatResponse(**response_data)

    except HTTPException:
        # Re-lanzar HTTPExceptions tal como están
        raise
    except WAHAAuthenticationError as e:
        logger.error(f"Error de autenticación WAHA: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autorizado: API Key de WAHA inválida",
        )
    except WAHATimeoutError as e:
        logger.error(f"Timeout WAHA: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout en la comunicación con WAHA",
        )
    except WAHAConnectionError as e:
        logger.error(f"Error de conexión WAHA: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio WAHA no disponible",
        )
    except Exception as e:
        logger.error(f"Error inesperado obteniendo chat {chat_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor",
        )


@router.delete(
    "/cache",
    status_code=status.HTTP_200_OK,
    summary="Limpiar cache de chats",
    description="""
    Limpia completamente el cache interno de chats para forzar la actualización de datos.
    
    **Casos de uso:**
    - Desarrollo y testing
    - Troubleshooting de datos obsoletos
    - Forzar actualización después de cambios en WAHA
    - Liberación de memoria en producción
    
    **Impacto:**
    - Todas las próximas consultas irán directamente a WAHA
    - Posible aumento temporal en latencia
    - Liberación inmediata de memoria cache
    """,
    responses={
        200: {
            "description": "Cache limpiado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Cache de chats limpiado exitosamente",
                        "cleared_entries": 45,
                        "timestamp": "2024-01-15T10:30:00.123456",
                    }
                }
            },
        }
    },
    tags=["Cache", "Admin"],
)
async def clear_chat_cache() -> Dict[str, Any]:
    """
    Limpia el cache de chats
    """
    cache = get_cache()
    cleared_entries = cache.clear()

    logger.info(f"Cache de chats limpiado - {cleared_entries} entradas eliminadas")

    return {
        "message": "Cache de chats limpiado exitosamente",
        "cleared_entries": cleared_entries,
        "timestamp": datetime.now().isoformat(),
    }


@router.get(
    "/health/status",
    status_code=status.HTTP_200_OK,
    summary="Estado de salud del servicio de chats",
    description="""
    Verifica el estado completo de salud del servicio de chats y todos sus componentes.
    
    **Componentes verificados:**
    - 🔗 Conectividad con WAHA
    - 📱 Estado de la sesión de WhatsApp
    - 💾 Estadísticas del sistema de caché
    - ⚡ Rendimiento del servicio
    
    **Información incluida:**
    - Estado de la conexión WAHA
    - Información de la sesión activa
    - Métricas de caché (hits, misses, tamaño)
    - Timestamp de la verificación
    """,
    responses={
        200: {
            "description": "Servicio completamente saludable",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "waha_connection": "connected",
                        "session": {
                            "status": "WORKING",
                            "name": "default",
                            "config": {"webhooks": ["http://localhost:8000/webhooks"]},
                        },
                        "cache": {
                            "total_entries": 25,
                            "hits": 150,
                            "misses": 45,
                            "hit_rate": 0.769,
                            "memory_usage": "2.5MB",
                        },
                        "timestamp": "2024-01-15T10:30:00.123456",
                        "uptime": "2h 15m 30s",
                    }
                }
            },
        },
        503: {
            "description": "Servicio no disponible o con problemas",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "waha_connection": "disconnected",
                        "error": "No se pudo conectar con el servicio WAHA",
                        "timestamp": "2024-01-15T10:30:00.123456",
                    }
                }
            },
        },
    },
    tags=["Health", "Monitoring"],
)
async def get_chat_service_health(
    waha_client: WAHAClient = Depends(get_waha_dependency),
) -> Dict[str, Any]:
    """
    Verifica el estado de salud del servicio de chats
    """
    try:
        # Verificar estado de WAHA
        session_status = await waha_client.get_session_status()
        cache = get_cache()
        cache_stats = cache.get_stats()

        health_data = {
            "service": "chats",
            "status": "healthy",
            "waha_connection": "connected",
            "session_status": session_status.get("status", "unknown"),
            "cache_stats": cache_stats,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info("Health check exitoso para servicio de chats")
        return health_data

    except Exception as e:
        logger.error(f"Health check falló: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de chats no disponible",
        )
