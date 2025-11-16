"""Endpoints para manejo de webhooks de WAHA en tiempo real"""

from fastapi import APIRouter, HTTPException, Request, status, BackgroundTasks
from typing import Dict, Any
from datetime import datetime
import json

from ...utils.logging_config import get_logger
from ...database.models import ChatModel, InteractionModel
from ...services.cache import get_cache
from ..models.webhooks import (
    MessageEvent,
    WebhookResponse,
)

# Logger específico para este módulo
logger = get_logger(__name__)

# Crear router
router = APIRouter(tags=["Webhooks"])


def _map_waha_message_type(raw_type: str | None) -> str:
    """Mapea el tipo de WAHA al tipo interno.

    WAHA usa valores como `chat` (texto) y `ptt` (nota de voz).
    Nuestro modelo espera `text`, `voice`, etc.
    """
    if not raw_type:
        return "text"
    mapping = {
        "chat": "text",
        "ptt": "voice",
    }
    return mapping.get(raw_type, raw_type)


async def process_webhook_event(event_type: str, event_data: Dict[str, Any]) -> None:
    """
    Process webhook events in background.
    """
    try:
        cache = get_cache()
        redis_client = cache.redis_client

        if event_type == "message":
            chat_id = event_data.get("from")
            if chat_id:
                interaction = None
                is_derived = False
                try:
                    interaction = InteractionModel.find_by_chat_id(chat_id)
                    is_derived = (
                        interaction is not None
                        and str(interaction.get("state", "")).lower() == "derived"
                    )
                except Exception:
                    interaction = None
                    is_derived = False

                if is_derived:
                    cache.delete_pattern(f"messages:{chat_id}:*")
                    cache.delete_pattern(f"chat:{chat_id}")
                    logger.info(f"Cache invalidated for chat: {chat_id}")

                # Persist incoming message in MongoDB
                try:
                    ChatModel.add_message(
                        chat_id,
                        {
                            "id": event_data.get("id"),
                            "body": event_data.get("body"),
                            "timestamp": event_data.get("timestamp", 0),
                            "type": event_data.get("type", "text"),
                            "from_me": bool(event_data.get("fromMe", False)),
                            "ack": event_data.get("ack"),
                            "from": event_data.get("from"),
                        },
                        interaction_id=(
                            interaction.get("_id") if (interaction and is_derived) else None
                        ),
                    )
                except Exception as e:
                    logger.warning(f"Failed to persist incoming message: {e}")

                # Publish real-time event to Redis channel for SSE subscribers
                try:
                    channel_name = f"{cache.key_prefix}stream:{chat_id}"
                    payload = {
                        "type": "message",
                        "chat_id": chat_id,
                        "interaction_id": (
                            interaction.get("_id") if (interaction and is_derived) else None
                        ),
                        "message": {
                            "id": event_data.get("id"),
                            "body": event_data.get("body"),
                            "timestamp": event_data.get("timestamp", 0),
                            "type": event_data.get("type", "text"),
                            "from_me": bool(event_data.get("fromMe", False)),
                            "from": event_data.get("from"),
                        },
                    }
                    redis_client.publish(channel_name, json.dumps(payload))
                except Exception as e:
                    logger.warning(
                        f"Failed to publish SSE event for chat {chat_id}: {e}"
                    )

        # Store event for potential later inspection
        event_key = f"webhook_event:{datetime.now().isoformat()}"
        cache.set(event_key, {"type": event_type, "data": event_data}, ttl=86400)

    except Exception as e:
        logger.error(f"Error processing webhook event {event_type}: {e}")


@router.post(
    "/waha",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Recibir eventos de WAHA",
    description="""
    Endpoint para recibir eventos en tiempo real desde WAHA.
    
    **Eventos soportados:**
    - `message`: Nuevo mensaje recibido
    - `message.ack`: Confirmación de mensaje enviado (ignorado por ahora)
    
    **Uso:** Este endpoint debe configurarse en WAHA como webhook URL.
    """,
    responses={
        200: {
            "description": "Evento procesado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Evento procesado exitosamente",
                        "event_type": "message",
                        "timestamp": "2024-01-15T10:30:00.123456",
                    }
                }
            },
        },
        400: {"description": "Datos de evento inválidos"},
        500: {"description": "Error interno del servidor"},
    },
)
async def receive_waha_webhook(
    request: Request, background_tasks: BackgroundTasks
) -> WebhookResponse:
    """
    Recibe y procesa eventos de webhook desde WAHA
    """
    try:
        # Obtener datos del webhook
        raw_data = await request.body()

        if not raw_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cuerpo de la petición vacío",
            )

        # Parsear JSON
        try:
            webhook_data = json.loads(raw_data)
        except json.JSONDecodeError as e:
            logger.warning(f"Error parseando JSON del webhook: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="JSON inválido en el cuerpo de la petición",
            )

        # Validar estructura básica
        event_type = webhook_data.get("event")
        if not event_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Campo 'event' requerido",
            )

        # Extraer payload (WAHA envía `payload`; también aceptamos `data` por compatibilidad)
        payload = webhook_data.get("payload") or webhook_data.get("data", {})

        # Validar y procesar según el tipo de evento
        event_data: Dict[str, Any] = {}

        if event_type == "message":
            try:
                # Normalizar campos al esquema esperado por MessageEvent
                raw_type = (payload.get("_data") or {}).get("type")
                normalized: Dict[str, Any] = {
                    "id": payload.get("id"),
                    "timestamp": payload.get("timestamp"),
                    "from": payload.get("from"),
                    "to": payload.get("to"),
                    "body": payload.get("body"),
                    # WAHA usa camelCase; nuestro modelo acepta alias fromMe
                    "fromMe": payload.get("fromMe"),
                    # Preferimos ackName (STRING) sobre ack (NUMBER)
                    "ack": payload.get("ackName") or payload.get("ack"),
                    "type": _map_waha_message_type(raw_type),
                }

                message_event = MessageEvent(**normalized)
                event_data = normalized
                logger.info(
                    f"Mensaje recibido de {message_event.from_user}: {message_event.body[:50]}..."
                )
            except Exception as e:
                logger.warning(
                    f"Error validando evento de mensaje: {e}. Payload recibido: {payload}"
                )

        elif event_type == "message.ack":
            # ACK events are ignored intentionally
            logger.info("ACK event received and ignored as per current configuration")

        else:
            logger.info(f"Tipo de evento no reconocido: {event_type}")

        # Procesar evento en segundo plano solo para 'message'
        if event_type == "message":
            background_tasks.add_task(process_webhook_event, event_type, event_data)

        return WebhookResponse(
            status="success",
            message="Evento procesado exitosamente",
            event_type=event_type,
            timestamp=datetime.now().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado procesando webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor",
        )


@router.get(
    "/events/recent",
    summary="Obtener eventos recientes",
    description="""
    Obtiene una lista de eventos de webhook recientes para debugging y monitoreo.
    
    **Uso:** Desarrollo, debugging, monitoreo de eventos en tiempo real.
    """,
    responses={
        200: {
            "description": "Lista de eventos recientes",
            "content": {
                "application/json": {
                    "example": {
                        "events": [
                            {
                                "timestamp": "2024-01-15T10:30:00.123456",
                                "type": "message",
                                "data": {"from": "1234567890@c.us", "body": "Hola"},
                            }
                        ],
                        "total": 1,
                    }
                }
            },
        }
    },
)
async def get_recent_events(limit: int = 10) -> Dict[str, Any]:
    """
    Obtiene eventos recientes del cache
    """
    try:
        cache = get_cache()

        # Buscar eventos recientes (últimas 24 horas)
        pattern = f"{cache.key_prefix}webhook_event:*"
        event_keys = cache.redis_client.keys(pattern)

        # Ordenar por timestamp (más recientes primero)
        event_keys.sort(reverse=True)

        # Limitar resultados
        if limit:
            event_keys = event_keys[:limit]

        # Construir respuesta
        events = []
        for key in event_keys:
            # Remover el prefijo para obtener la clave original
            original_key = key.replace(cache.key_prefix, "")
            event_data = cache.get(original_key)
            if event_data:
                timestamp = original_key.replace("webhook_event:", "")
                events.append(
                    {
                        "timestamp": timestamp,
                        "type": event_data.get("type"),
                        "data": event_data.get("data"),
                    }
                )

        return {"events": events, "total": len(events)}

    except Exception as e:
        logger.error(f"Error obteniendo eventos recientes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor",
        )


@router.delete(
    "/events",
    summary="Limpiar eventos almacenados",
    description="Limpia todos los eventos de webhook almacenados en cache.",
    responses={
        200: {
            "description": "Eventos limpiados exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Eventos limpiados exitosamente",
                        "cleared_count": 25,
                    }
                }
            },
        }
    },
)
async def clear_webhook_events() -> Dict[str, Any]:
    """
    Limpia todos los eventos de webhook del cache
    """
    try:
        cache = get_cache()

        # Buscar y eliminar todos los eventos usando delete_pattern
        pattern = "webhook_event:*"
        cleared_count = cache.delete_pattern(pattern)

        logger.info(f"Limpiados {cleared_count} eventos de webhook")

        return {
            "message": "Eventos limpiados exitosamente",
            "cleared_count": cleared_count,
        }

    except Exception as e:
        logger.error(f"Error limpiando eventos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor",
        )
