"""Endpoints para gestión de chats de WhatsApp"""

from fastapi import APIRouter, HTTPException, Query, Path, Depends, status
from typing import Dict, Any
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
    MessagesListResponse,
    SendMessageRequest,
    SendMessageResponse,
    Message,
)
from ...utils.logging_config import get_logger
from .auth import get_current_user, get_current_admin
from ...database.models import InteractionModel, ChatModel

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


@router.delete(
    "/cache",
    status_code=status.HTTP_200_OK,
    summary="Limpiar cache de chats",
    description="""
    Limpia completamente el cache interno de chats para forzar la actualización de datos.
    
    **Uso:** Desarrollo, testing, troubleshooting de datos obsoletos y liberación de memoria.
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
async def clear_chat_cache(
    current_admin: dict = Depends(get_current_admin),
) -> Dict[str, Any]:
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
    "",
    response_model=ChatListResponse,
    summary="Obtener lista de chats",
    description="Obtiene una lista paginada de chats de WhatsApp desde WAHA API con caché optimizado.",
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
    current_user: dict = Depends(get_current_user),
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

        # Obtener chats desde WAHA (paginados) y normalizar a ChatOverview
        raw_chats = await waha_client.get_chats(limit=limit, offset=offset)

        normalized_chats = []
        for raw_chat in raw_chats:
            try:
                normalized_data = waha_client._normalize_chat_data(raw_chat)
                overview_data = {
                    "id": normalized_data.get("id", ""),
                    "name": normalized_data.get("name"),
                    "type": normalized_data.get("type", "individual"),
                    "timestamp": normalized_data.get("timestamp"),
                    "unread_count": normalized_data.get("unread_count", 0),
                    "last_message": normalized_data.get("last_message"),
                    "picture_url": normalized_data.get("picture_url"),
                    "archived": normalized_data.get("archived", False),
                    "pinned": normalized_data.get("pinned", False),
                }
                chat_overview = ChatOverview(**overview_data)
                normalized_chats.append(chat_overview)
            except Exception as e:
                logger.warning(
                    f"Error normalizando chat {raw_chat.get('id', 'unknown')}: {e}"
                )
                continue

        # Integrate interactions with 'pending' state
        try:
            pending_total = InteractionModel.count_all(state="pending")
            pending_interactions = (
                InteractionModel.find_all(skip=0, limit=pending_total, state="pending")
                if pending_total > 0
                else []
            )

            # Build the set of ids for pending interactions using chat_id or phone
            pending_ids = set()
            for it in pending_interactions:
                cid = it.get("chat_id") or it.get("phone")
                if cid:
                    pending_ids.add(cid)

            # Filter WAHA chats to include only those with pending interactions
            chats_by_id = {c.id: c for c in normalized_chats}
            filtered_chats = [c for c in normalized_chats if c.id in pending_ids]

            # Add minimal chats based on pending interactions that are not present in WAHA
            for it in pending_interactions:
                # Prefer chat_id; fallback to phone when chat_id is missing
                chat_id = it.get("chat_id") or it.get("phone")
                if not chat_id or chat_id in chats_by_id:
                    continue

                # Build a minimal ChatOverview from interaction data
                created_at = it.get("createdAt")
                timestamp = None
                try:
                    if created_at:
                        # Convert datetime to unix timestamp (seconds)
                        timestamp = int(created_at.timestamp())
                except Exception:
                    timestamp = None

                minimal_chat_data = {
                    "id": chat_id,
                    "name": it.get("phone"),
                    "type": "individual",
                    "timestamp": timestamp,
                    "unread_count": 0,
                    "archived": False,
                    "pinned": False,
                    "muted": False,
                    "contact": None,
                    "last_message": None,
                    "participants": None,
                    "group_metadata": None,
                    "picture_url": None,
                }

                try:
                    fallback_chat = ChatOverview(**minimal_chat_data)
                    filtered_chats.append(fallback_chat)
                except Exception as e:
                    logger.warning(
                        f"Error creating chat from pending interaction {chat_id}: {e}"
                    )

            # Ordenar por timestamp descendente cuando esté disponible
            def sort_key(c: ChatOverview):
                return c.timestamp or 0

            filtered_chats.sort(key=sort_key, reverse=True)

            normalized_chats = filtered_chats
        except Exception as e:
            logger.warning(f"No se pudo integrar interacciones pendientes en chats: {e}")

        # Aplicar paginación al resultado combinado
        total_count = len(normalized_chats)
        paged_chats = normalized_chats[offset : offset + limit]

        # Crear respuesta (serialize chats for cache)
        response_data = {
            "chats": [chat.dict() for chat in paged_chats],
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count,
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
    
    **Características:** Respuesta más rápida que el endpoint completo, solo información esencial de cada chat, ideal para listados y navegación con cache optimizado de 5 minutos.
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
    current_user: dict = Depends(get_current_user),
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
    
    **Incluye:** Información completa del chat, detalles del contacto o grupo, último mensaje si está disponible y cache optimizado de 10 minutos.
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
    current_user: dict = Depends(get_current_user),
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


@router.get(
    "/health/status",
    status_code=status.HTTP_200_OK,
    summary="Estado de salud del servicio de chats",
    description="""
    Verifica el estado completo de salud del servicio de chats y todos sus componentes.
    
    **Componentes verificados:** Conectividad con WAHA, estado de la sesión de WhatsApp, estadísticas del sistema de caché y rendimiento del servicio.
    
    **Información incluida:** Estado de la conexión WAHA, información de la sesión activa, métricas de caché y timestamp de la verificación.
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
    current_user: dict = Depends(get_current_user),
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


@router.get(
    "/{chat_id}/messages",
    response_model=MessagesListResponse,
    summary="Obtener mensajes de un chat",
    description="""
    Obtiene los mensajes de un chat específico con paginación.
    
    **Características:** Lista paginada de mensajes ordenados por timestamp (más recientes primero) con información completa de cada mensaje y soporte para diferentes tipos.
    """,
    responses={
        200: {"description": "Mensajes obtenidos exitosamente"},
        404: {"description": "Chat no encontrado"},
        503: {"description": "Servicio WAHA no disponible"},
        500: {"description": "Error interno del servidor"},
    },
)
async def get_chat_messages(
    chat_id: str = Path(..., description="ID único del chat"),
    limit: int = Query(
        20, ge=1, le=100, description="Número máximo de mensajes a obtener"
    ),
    offset: int = Query(0, ge=0, description="Desplazamiento para paginación"),
    waha_client: WAHAClient = Depends(get_waha_dependency),
    current_user: dict = Depends(get_current_user),
) -> MessagesListResponse:
    """
    Obtiene mensajes de un chat específico
    """
    try:
        logger.info(f"Obteniendo mensajes para chat: {chat_id}")

        # Obtener mensajes desde WAHA
        messages_data = await waha_client.get_messages(chat_id, limit, offset)

        # Normalizar mensajes
        messages = []
        for msg_data in messages_data.get("messages", []):
            message = Message(
                id=msg_data.get("id", ""),
                body=msg_data.get("body"),
                timestamp=msg_data.get("timestamp", 0),
                from_me=msg_data.get("fromMe", False),
                type=msg_data.get("type", "text"),
                from_contact=msg_data.get("from"),
                ack=msg_data.get("ack"),
            )
            messages.append(message)

        response = MessagesListResponse(
            messages=messages,
            total=messages_data.get("total", 0),
            limit=limit,
            offset=offset,
        )

        logger.info(f"Mensajes obtenidos exitosamente: {len(messages)} mensajes")
        return response

    except WAHANotFoundError:
        logger.warning(f"Chat no encontrado: {chat_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat no encontrado",
        )
    except WAHATimeoutError:
        logger.error(f"Timeout obteniendo mensajes para chat: {chat_id}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout en comunicación con WAHA",
        )
    except WAHAConnectionError:
        logger.error(f"Error de conexión obteniendo mensajes para chat: {chat_id}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio WAHA no disponible",
        )
    except Exception as e:
        logger.error(f"Error inesperado obteniendo mensajes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor",
        )


@router.get(
    "/{chat_id}/messages/db",
    response_model=MessagesListResponse,
    summary="Obtener mensajes persistidos de un chat",
    description="Obtiene los mensajes almacenados en MongoDB para un chat específico.",
    responses={
        200: {"description": "Mensajes obtenidos exitosamente"},
        404: {"description": "Chat no encontrado"},
        500: {"description": "Error interno del servidor"},
    },
)
async def get_chat_messages_db(
    chat_id: str = Path(
        ...,
        description="ID único del chat",
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9@._-]+$",
    ),
    limit: int = Query(20, ge=1, le=100, description="Número máximo de mensajes"),
    offset: int = Query(0, ge=0, description="Desplazamiento para paginación"),
    current_user: dict = Depends(get_current_user),
) -> MessagesListResponse:
    """
    Obtiene mensajes persistidos de un chat específico desde MongoDB
    """
    try:
        data = ChatModel.get_messages(chat_id, limit, offset)
        messages = []
        for msg in data.get("messages", []):
            messages.append(
                Message(
                    id=msg.get("id", ""),
                    body=msg.get("body"),
                    timestamp=msg.get("timestamp", 0),
                    from_me=bool(msg.get("from_me", False)),
                    type=msg.get("type", "text"),
                    from_contact=msg.get("from"),
                    ack=msg.get("ack"),
                )
            )

        return MessagesListResponse(
            messages=messages,
            total=data.get("total", 0),
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error(f"Error obteniendo mensajes persistidos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor",
        )


@router.post(
    "/{chat_id}/messages",
    response_model=SendMessageResponse,
    summary="Enviar mensaje a un chat",
    description="""
    Envía un mensaje a un chat específico con soporte para diferentes tipos de mensaje.
    
    **Tipos soportados:** texto, imagen, video, audio, documento, ubicación, contacto, sticker.
    
    **Validaciones:** Los mensajes multimedia requieren media_url, los de ubicación requieren coordenadas.
    """,
    responses={
        200: {
            "description": "Mensaje enviado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "id": "msg_123456789",
                        "status": "sent",
                        "timestamp": 1642234567,
                    }
                }
            },
        },
        404: {
            "description": "Chat no encontrado",
            "content": {
                "application/json": {"example": {"detail": "Chat no encontrado"}}
            },
        },
        422: {
            "description": "Datos de entrada inválidos",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_media_url": {
                            "summary": "URL multimedia faltante",
                            "value": {
                                "detail": [
                                    {
                                        "loc": ["body", "media_url"],
                                        "msg": "Los mensajes de tipo image requieren media_url",
                                        "type": "value_error",
                                    }
                                ]
                            },
                        },
                        "missing_coordinates": {
                            "summary": "Coordenadas faltantes",
                            "value": {
                                "detail": [
                                    {
                                        "loc": ["body", "latitude"],
                                        "msg": "Los mensajes de ubicación requieren latitud",
                                        "type": "value_error",
                                    }
                                ]
                            },
                        },
                    }
                }
            },
        },
        503: {"description": "Servicio WAHA no disponible"},
        500: {"description": "Error interno del servidor"},
    },
)
async def send_message(
    chat_id: str = Path(
        ...,
        description="ID único del chat",
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9@._-]+$",
    ),
    message_request: SendMessageRequest = ...,
    waha_client: WAHAClient = Depends(get_waha_dependency),
    current_user: dict = Depends(get_current_user),
) -> SendMessageResponse:
    """
    Envía un mensaje a un chat específico con validación completa
    """
    try:
        logger.info(f"Enviando mensaje tipo '{message_request.type}' a chat: {chat_id}")

        # Preparar datos del mensaje según el tipo
        message_data = {
            "text": message_request.message,
            "type": message_request.type.value,
        }

        # Agregar campos específicos según el tipo de mensaje
        if message_request.type == MessageType.LOCATION:
            message_data.update(
                {
                    "latitude": message_request.latitude,
                    "longitude": message_request.longitude,
                }
            )

        if message_request.type in [
            MessageType.IMAGE,
            MessageType.VIDEO,
            MessageType.AUDIO,
            MessageType.DOCUMENT,
        ]:
            message_data["media_url"] = message_request.media_url
            if message_request.caption:
                message_data["caption"] = message_request.caption
            if message_request.filename:
                message_data["filename"] = message_request.filename

        # Agregar metadatos opcionales
        if message_request.reply_to:
            message_data["reply_to"] = message_request.reply_to

        if message_request.metadata:
            message_data["metadata"] = message_request.metadata

        # Enviar mensaje a través de WAHA
        result = await waha_client.send_message(
            chat_id,
            message_request.message,
            message_request.type.value,
            **{k: v for k, v in message_data.items() if k not in ["text", "type"]},
        )

        # Persistir mensaje en MongoDB (saliente)
        try:
            interaction = InteractionModel.find_by_chat_id(chat_id)
            advisor_id = str(current_user.get("_id")) if current_user.get("_id") else None
            ChatModel.add_message(
                chat_id,
                {
                    "id": result.get("id"),
                    "body": message_request.message,
                    "timestamp": result.get("timestamp", 0),
                    "type": message_request.type.value,
                    "from_me": True,
                    "ack": result.get("ack"),
                    "metadata": message_request.metadata,
                    "advisor_id": advisor_id,
                },
                interaction_id=interaction.get("_id") if interaction else None,
            )
        except Exception as persist_err:
            logger.warning(f"No se pudo persistir el mensaje en Mongo: {persist_err}")

        response = SendMessageResponse(
            id=result.get("id", ""),
            status=result.get("status", "sent"),
            timestamp=result.get("timestamp", 0),
        )

        logger.info(
            f"Mensaje '{message_request.type}' enviado exitosamente: {response.id}"
        )
        return response

    except ValueError as e:
        # Errores de validación del modelo
        logger.warning(f"Error de validación enviando mensaje: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except WAHANotFoundError:
        logger.warning(f"Chat no encontrado para envío: {chat_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat no encontrado",
        )
    except WAHATimeoutError:
        logger.error(f"Timeout enviando mensaje a chat: {chat_id}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout en comunicación con WAHA",
        )
    except WAHAConnectionError:
        logger.error(f"Error de conexión enviando mensaje a chat: {chat_id}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio WAHA no disponible",
        )
    except Exception as e:
        logger.error(f"Error inesperado enviando mensaje: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor",
        )
