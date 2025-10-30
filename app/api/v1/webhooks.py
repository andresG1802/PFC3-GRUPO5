"""Endpoints para manejo de webhooks de WAHA en tiempo real"""

from fastapi import APIRouter, HTTPException, Request, status, BackgroundTasks
from typing import Dict, Any, Optional
from datetime import datetime
import json

from ...utils.logging_config import get_logger
from ...services.cache import get_cache
from ..models.webhooks import (
    WebhookEvent,
    MessageEvent,
    MessageAckEvent,
    SessionStatusEvent,
    PresenceUpdateEvent,
    WebhookResponse,
)

# Logger específico para este módulo
logger = get_logger(__name__)

# Crear router
router = APIRouter(tags=["Webhooks"])


async def process_webhook_event(event_type: str, event_data: Dict[str, Any]) -> None:
    """
    Procesa eventos de webhook en segundo plano
    """
    try:
        cache = get_cache()

        if event_type == "message":
            # Invalidar cache de mensajes del chat afectado
            chat_id = event_data.get("from")
            if chat_id:
                cache.delete_pattern(f"messages:{chat_id}:*")
                cache.delete_pattern(f"chat:{chat_id}")
                logger.info(f"Cache invalidado para chat: {chat_id}")

        elif event_type == "message.ack":
            # Actualizar estado de mensaje
            message_id = event_data.get("id")
            if message_id:
                cache.delete_pattern(f"message:{message_id}")
                logger.info(f"Cache de mensaje actualizado: {message_id}")

        elif event_type == "session.status":
            # Actualizar estado de sesión
            session = event_data.get("session")
            status_value = event_data.get("status")
            if session:
                cache.set(f"session:{session}:status", status_value, ttl=3600)
                logger.info(
                    f"Estado de sesión actualizado: {session} -> {status_value}"
                )

        elif event_type == "presence.update":
            # Actualizar presencia de contacto
            contact_id = event_data.get("id")
            presence = event_data.get("presence")
            if contact_id:
                cache.set(f"presence:{contact_id}", presence, ttl=300)
                logger.info(f"Presencia actualizada: {contact_id} -> {presence}")

        # Almacenar evento para posible procesamiento posterior
        event_key = f"webhook_event:{datetime.now().isoformat()}"
        cache.set(event_key, {"type": event_type, "data": event_data}, ttl=86400)

    except Exception as e:
        logger.error(f"Error procesando evento webhook {event_type}: {e}")


@router.post(
    "/waha",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Recibir eventos de WAHA",
    description="""
    Endpoint para recibir eventos en tiempo real desde WAHA.
    
    **Eventos soportados:**
    - `message`: Nuevo mensaje recibido
    - `message.ack`: Confirmación de mensaje enviado
    - `session.status`: Cambio de estado de sesión
    - `presence.update`: Actualización de presencia de contacto
    
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

        # Validar y procesar según el tipo de evento
        event_data = webhook_data.get("data", {})

        if event_type == "message":
            try:
                message_event = MessageEvent(**event_data)
                logger.info(
                    f"Mensaje recibido de {message_event.from_user}: {message_event.body[:50]}..."
                )
            except Exception as e:
                logger.warning(f"Error validando evento de mensaje: {e}")

        elif event_type == "message.ack":
            try:
                ack_event = MessageAckEvent(**event_data)
                logger.info(
                    f"ACK recibido para mensaje {ack_event.id}: {ack_event.ack}"
                )
            except Exception as e:
                logger.warning(f"Error validando evento ACK: {e}")

        elif event_type == "session.status":
            try:
                session_event = SessionStatusEvent(**event_data)
                logger.info(
                    f"Estado de sesión {session_event.session}: {session_event.status}"
                )
            except Exception as e:
                logger.warning(f"Error validando evento de sesión: {e}")

        elif event_type == "presence.update":
            try:
                presence_event = PresenceUpdateEvent(**event_data)
                logger.info(
                    f"Presencia actualizada {presence_event.id}: {presence_event.presence}"
                )
            except Exception as e:
                logger.warning(f"Error validando evento de presencia: {e}")

        else:
            logger.info(f"Tipo de evento no reconocido: {event_type}")

        # Procesar evento en segundo plano
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
