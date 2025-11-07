"""Endpoints para gestión de chats de WhatsApp"""

from fastapi import APIRouter, HTTPException, Query, Path, Depends, status
from typing import Dict, Any
from datetime import datetime, timezone

from app.api import envs

from ...services.waha_client import (
    get_waha_client,
    WAHAClient,
    WAHAConnectionError,
    WAHANotFoundError,
    WAHATimeoutError,
)
from ...services.cache import (
    get_cache,
    cache_key_for_overview,
)
from ..models.chats import (
    ChatOverview,
    ErrorResponse,
    MessagesListResponse,
    SendMessageRequest,
    SendMessageResponse,
    Message,
    MessageType,
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
    Uso recomendado: Desarrollo, testing, troubleshooting de datos obsoletos y liberación de memoria.
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
    }
)
async def clear_chat_cache(
    current_admin: dict = Depends(get_current_admin),
) -> Dict[str, Any]:
    """
    Limpia el cache de chats
    """
    if not envs.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cache clearing is only available in DEBUG mode",
        )
    cache = get_cache()
    cleared_entries = cache.clear()

    logger.info(f"Cache de chats limpiado - {cleared_entries} entradas eliminadas")

    return {
        "message": "Cache de chats limpiado exitosamente",
        "cleared_entries": cleared_entries,
        "timestamp": datetime.now().isoformat(),
    }


@router.get(
    "/overview",
    summary="Get chats overview",
    description=(
        "Gets an optimized chats overview from WAHA. If pending interactions exist in the database, "
        "the request applies an 'ids' filter built from interaction phone numbers as stored ('<phone>@<domain>') "
        "so WAHA only returns overview for those contacts. Each chat includes the related MongoDB interaction '_id' when available."
    ),
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
                                    "interaction_id": "665f1a2b3c4d5e6f7a8b9c0d",
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
    }
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
        # Construir filtro de IDs desde interacciones (usar 'phone') y mapear _id
        ids_filter_set = set()
        interaction_id_map: dict[str, str] = {}
        try:
            total_interactions = InteractionModel.count_all(state="pending")
            interactions = (
                InteractionModel.find_all(
                    skip=0, limit=total_interactions, state="pending"
                )
                if total_interactions and total_interactions > 0
                else []
            )
            for it in interactions:
                phone = (it.get("phone") or "").strip()
                chat_id = (it.get("chat_id") or "").strip()
                mongo_id = it.get("_id")
                if phone:
                    ids_filter_set.add(phone)
                    if mongo_id:
                        interaction_id_map[phone] = str(mongo_id)
                elif chat_id and "@" in chat_id:
                    ids_filter_set.add(chat_id)
                    if mongo_id:
                        interaction_id_map[chat_id] = str(mongo_id)
        except Exception:
            ids_filter_set = set()

        ids_filter = list(ids_filter_set)

        # Verificar cache con clave sensible al filtro de ids
        cache = get_cache()
        cache_key = cache_key_for_overview(
            limit, offset, ids_filter if ids_filter else None
        )
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

        # Intentar obtener overview optimizado con filtro por ids; fallback a overview sin filtro o a chats normales
        try:
            if ids_filter:
                raw_chats = await waha_client.get_chats_overview(
                    limit=limit, offset=offset, ids=ids_filter
                )
            else:
                raw_chats = await waha_client.get_chats_overview(
                    limit=limit, offset=offset
                )
        except Exception:
            logger.warning("Overview no disponible, usando chats normales")
            raw_chats = await waha_client.get_chats(limit=limit, offset=offset)

        # Si hubo fallback y tenemos filtro, aplicar filtrado local por id
        if ids_filter:
            allowed_ids = set(ids_filter)
            try:
                raw_chats = [c for c in raw_chats if c.get("id") in allowed_ids]
            except Exception:
                pass

        # Crear objetos ChatOverview y enriquecer con interaction_id
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
                chat_obj = ChatOverview(**overview_data)
                chat_dict = chat_obj.dict()
                # Añadir _id de interacción si existe
                interaction_id = interaction_id_map.get(chat_dict.get("id"))
                if interaction_id:
                    chat_dict["interaction_id"] = interaction_id
                overview_chats.append(chat_dict)
            except Exception as e:
                logger.warning(
                    f"Error creando overview para chat {raw_chat.get('id', 'unknown')}: {e}"
                )
                continue

        # Guardar en cache
        cache.set(cache_key, overview_chats, ttl=300)

        # Crear respuesta estructurada
        response_data = {
            "success": True,
            "data": {
                "summary": {
                    "total_chats": len(overview_chats),
                    "limit": limit,
                    "offset": offset,
                },
                "chats": overview_chats,
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
    "/{interaction_id}",
    response_model=MessagesListResponse,
    summary="Get persisted chat messages by interaction",
    description="""
    Returns persisted messages from MongoDB for the chat associated with the given interaction.

    Chat ID resolution:
    - Try `interaction_id` as key.
    - Fallback: load the interaction and use `chat_id` or `phone` as chat identifier.

    Pagination: `limit` and `offset`. No caching to avoid stale data.
    """,
    responses={
        200: {"description": "Messages retrieved successfully"},
        404: {"description": "Chat not found"},
        500: {"description": "Internal server error"},
    }
)
async def get_chat_by_id(
    interaction_id: str = Path(
        ...,
        description="Unique interaction ID (MongoDB ObjectId)",
        min_length=24,
        max_length=24,
        pattern=r"^[a-fA-F0-9]{24}$",
    ),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of messages"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: dict = Depends(get_current_user),
) -> MessagesListResponse:
    """
    Get persisted messages for the chat associated with an interaction.
    """
    try:
        logger.info(
            f"Obteniendo mensajes por interaction_id: {interaction_id} (limit={limit}, offset={offset})"
        )

        # Resolver posibles claves de chat
        candidates = [interaction_id]
        interaction = InteractionModel.find_by_id(interaction_id)
        if interaction:
            chat_id_ref = (interaction.get("chat_id") or "").strip()
            phone_ref = (interaction.get("phone") or "").strip()
            if chat_id_ref:
                candidates.append(chat_id_ref)
            if phone_ref:
                candidates.append(phone_ref)

        # Intentar obtener mensajes usando la primera clave válida que exista en DB
        for candidate in candidates:
            chat_exists = ChatModel.get_chat(candidate)
            if chat_exists:
                data = ChatModel.get_messages(candidate, limit, offset)
                messages = []
                for msg in data.get("messages", []):
                    # Normalizar ID (puede venir como objeto con 'serialized'/_serialized)
                    raw_id = msg.get("id", "")
                    if isinstance(raw_id, dict):
                        norm_id = (
                            raw_id.get("serialized")
                            or raw_id.get("_serialized")
                            or raw_id.get("id")
                            or ""
                        )
                    else:
                        norm_id = raw_id if isinstance(raw_id, str) else str(raw_id)

                    # Normalizar ACK numérico a enum string
                    raw_ack = msg.get("ack")
                    ack_map = {
                        -1: "ERROR",
                        0: "PENDING",
                        1: "SERVER",
                        2: "DEVICE",
                        3: "READ",
                        4: "PLAYED",
                    }
                    norm_ack = (
                        ack_map.get(raw_ack, "PENDING")
                        if isinstance(raw_ack, int)
                        else raw_ack
                    )

                    # Normalizar 'from_me' (puede venir como 'fromMe')
                    from_me_val = bool(msg.get("from_me", msg.get("fromMe", False)))

                    messages.append(
                        Message(
                            id=norm_id,
                            body=msg.get("body"),
                            timestamp=msg.get("timestamp", 0),
                            from_me=from_me_val,
                            type=msg.get("type", "text"),
                            from_contact=msg.get("from"),
                            ack=norm_ack,
                        )
                    )

                # Construir summary si hay interacción
                summary_message = None
                if interaction:
                    summary_message = _build_interaction_summary(
                        interaction.get("timeline", []), interaction.get("route")
                    )

                logger.info(
                    f"Mensajes obtenidos (chat_id='{candidate}'): total={data.get('total', 0)}"
                )
                return MessagesListResponse(
                    messages=messages,
                    total=data.get("total", 0),
                    limit=limit,
                    offset=offset,
                    summary=summary_message,
                    chat_id=candidate,
                )

        # Si no existe chat pero la interacción está pending, devolver mensajes vacíos y summary
        if interaction and interaction.get("state") == "pending":
            inferred_chat_id = (interaction.get("phone") or "").strip()
            summary_message = _build_interaction_summary(
                interaction.get("timeline", []), interaction.get("route")
            )
            logger.info(
                f"Interacción pending: devolviendo mensajes vacíos y summary (interaction_id='{interaction_id}')"
            )
            return MessagesListResponse(
                messages=[],
                total=0,
                limit=limit,
                offset=offset,
                summary=summary_message,
                chat_id=inferred_chat_id,
            )

        # Ninguna clave de chat válida encontrada
        logger.warning(
            f"Chat no encontrado para interaction_id='{interaction_id}' (candidatos: {candidates})"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat no encontrado",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error inesperado obteniendo mensajes para interaction_id {interaction_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor",
        )


@router.get(
    "/health/status",
    status_code=status.HTTP_200_OK,
    summary="Estado de salud del servicio de chats",
    description="Verifica el estado completo de salud del servicio de chats y todos sus componentes.",
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
    }
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info("Health check exitoso para servicio de chats")
        return health_data

    except Exception as e:
        logger.error(f"Health check falló: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de chats no disponible",
        )


# Endpoints GET de mensajes por chat_id han sido deprecados y retirados.


@router.post(
    "/{chat_id}/messages",
    response_model=SendMessageResponse,
    summary="Enviar mensaje a un chat",
    description="""
    Envía un mensaje a un chat específico con soporte para diferentes tipos de mensaje.
    Tipos soportados: texto, imagen, video, audio, documento, ubicación, contacto, sticker.
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
    chat_id: str = Path(..., description="ID único del chat"),
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
            advisor_id = (
                str(current_user.get("_id")) if current_user.get("_id") else None
            )
            # Normalizar ID del resultado (puede ser objeto con 'serialized'/_serialized)
            raw_id = result.get("id", "")
            if isinstance(raw_id, dict):
                norm_id = (
                    raw_id.get("serialized")
                    or raw_id.get("_serialized")
                    or raw_id.get("id")
                    or ""
                )
            else:
                norm_id = raw_id if isinstance(raw_id, str) else str(raw_id)

            # Normalizar ACK numérico a enum string
            raw_ack = result.get("ack")
            ack_map = {
                -1: "ERROR",
                0: "PENDING",
                1: "SERVER",
                2: "DEVICE",
                3: "READ",
                4: "PLAYED",
            }
            norm_ack = ack_map.get(raw_ack, "PENDING") if isinstance(raw_ack, int) else raw_ack

            ChatModel.add_message(
                chat_id,
                {
                    "id": norm_id,
                    "body": message_request.message,
                    "timestamp": result.get("timestamp", 0),
                    "type": message_request.type.value,
                    "from_me": True,
                    "ack": norm_ack,
                    "metadata": message_request.metadata,
                    "advisor_id": advisor_id,
                },
                interaction_id=interaction.get("_id") if interaction else None,
            )
        except Exception as persist_err:
            logger.warning(f"No se pudo persistir el mensaje en Mongo: {persist_err}")

        # Construir respuesta con ID normalizado
        response = SendMessageResponse(
            id=norm_id,
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


def _build_interaction_summary(timeline: list, current_route: str | None) -> str:
    """Generate a human-readable paragraph summary based on timeline and route.

    Notes:
    - Ignore entries with route == 'route_1'.
    - Prefer the current interaction route if it is one of route_2/route_3/route_4.
    - Otherwise, select the most recent (last) route in the timeline among route_2/route_3/route_4.
    - Build a cohesive paragraph tailored to each route using available steps.
    """

    allowed_routes = {"route_2", "route_3", "route_4"}
    type_by_route = {
        "route_2": "abuso sexual",
        "route_3": "denuncia penal",
        "route_4": "deuda de alimentos",
    }

    # Choose target route
    target_route = None
    if current_route in allowed_routes:
        target_route = current_route
    else:
        for entry in reversed(timeline or []):
            r = (entry or {}).get("route")
            if r in allowed_routes:
                target_route = r
                break

    if not target_route:
        return "No hay información suficiente para generar el resumen."

    # Collect step -> userInput for the target route
    steps: dict[int, str] = {}
    for entry in timeline or []:
        if (entry or {}).get("route") != target_route:
            continue
        step_num = (entry or {}).get("step")
        user_input = (entry or {}).get("userInput")
        if step_num is None:
            continue
        steps[int(step_num)] = (user_input or "").strip()

    # Helper to translate numeric codes into human-readable text per route/step
    def _translate_input(route: str, step: int, raw_value: str) -> str:
        """Translate coded user inputs to human-readable labels based on route/step.

        Rules (English):
        - step 1 (all routes): 1 => "consulta", 2 => "denuncia".
        - route_2 step 2: 1 => "victima", 2 => "testigo".
        - route_3 step 2: 1 => "victima", 2 => "testigo".
        - route_3 step 3: 1 => "robo", 2 => "agresión física", 3 => "amenaza".
        - route_4 step 2: 1 => "sí", 2 => "no".
        - route_4 step 3: 1 => "sí", 2 => "no".
        - For any other case or free-text inputs, return the raw value.
        """

        v = (raw_value or "").strip()
        if v == "":
            return v

        # Common step 1 mapping
        if step == 1:
            return {"1": "consulta", "2": "denuncia"}.get(v, v)

        if route == "route_2" and step == 2:
            return {"1": "victima", "2": "testigo"}.get(v, v)

        if route == "route_3":
            if step == 2:
                return {"1": "victima", "2": "testigo"}.get(v, v)
            if step == 3:
                return {"1": "robo", "2": "agresión física", "3": "amenaza"}.get(v, v)

        if route == "route_4":
            if step == 2:
                return {"1": "sí", "2": "no"}.get(v, v)
            if step == 3:
                return {"1": "sí", "2": "no"}.get(v, v)

        return v

    tipo = type_by_route.get(target_route, target_route)

    # Compose paragraph by route
    if target_route == "route_2":
        # abuso sexual
        s1 = _translate_input(target_route, 1, steps.get(1, ""))
        s2 = _translate_input(target_route, 2, steps.get(2, ""))
        s3 = steps.get(3)
        parts: list[str] = []
        parts.append(f"Tipo de denuncia: {tipo}.")
        if s1:
            parts.append(f"El usuario indicó que desea realizar una {s1}.")
        if s2:
            parts.append(f"La persona se identifica como {s2}.")
        if s3:
            parts.append(f"Información adicional: {s3}.")
        return " ".join(parts)

    if target_route == "route_3":
        # denuncia penal
        s1 = _translate_input(target_route, 1, steps.get(1, ""))
        s2 = _translate_input(target_route, 2, steps.get(2, ""))
        s3 = _translate_input(target_route, 3, steps.get(3, ""))
        s4 = steps.get(4)
        parts: list[str] = []
        parts.append(f"Tipo de denuncia: {tipo}.")
        if s1:
            parts.append(f"El usuario indicó que desea realizar una {s1}.")
        if s2:
            parts.append(f"La persona es {s2}.")
        if s3:
            parts.append(f"Tipo de delito: {s3}.")
        if s4:
            parts.append(f"Información adicional: {s4}.")
        return " ".join(parts)

    if target_route == "route_4":
        # deuda de alimentos
        s1 = _translate_input(target_route, 1, steps.get(1, ""))
        s2 = _translate_input(target_route, 2, steps.get(2, ""))
        s3 = _translate_input(target_route, 3, steps.get(3, ""))
        s4 = steps.get(4)
        parts: list[str] = []
        parts.append(f"Tipo de denuncia: {tipo}.")
        if s1:
            parts.append(f"El usuario indicó que desea realizar una {s1}.")
        if s2:
            parts.append(f"Responsable de los menores: {s2}.")
        if s3:
            parts.append(f"Sentencia existente: {s3}.")
        if s4:
            parts.append(f"Información adicional: {s4}.")
        return " ".join(parts)

    # Fallback (should not happen given allowed_routes)
    return "No hay información suficiente para generar el resumen."
