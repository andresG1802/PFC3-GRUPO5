"""
Modelos Pydantic para eventos de webhook de WAHA
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from enum import Enum

from .chats import MessageType, MessageAck


class SessionStatus(str, Enum):
    """Estados de sesión de WhatsApp"""

    STARTING = "STARTING"
    SCAN_QR_CODE = "SCAN_QR_CODE"
    WORKING = "WORKING"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


class PresenceStatus(str, Enum):
    """Estados de presencia de contacto"""

    ONLINE = "online"
    OFFLINE = "offline"
    TYPING = "typing"
    RECORDING = "recording"
    PAUSED = "paused"


class WebhookEvent(BaseModel):
    """Modelo base para eventos de webhook"""

    event: str = Field(..., description="Tipo de evento")
    session: Optional[str] = Field(None, description="Sesión de WhatsApp")
    timestamp: Optional[int] = Field(None, description="Timestamp del evento")


class MessageEvent(BaseModel):
    """Evento de mensaje recibido"""

    id: str = Field(..., description="ID único del mensaje")
    timestamp: int = Field(..., description="Timestamp del mensaje")
    from_user: str = Field(..., alias="from", description="Remitente del mensaje")
    to: str = Field(..., description="Destinatario del mensaje")
    body: Optional[str] = Field(None, description="Contenido del mensaje")
    type: MessageType = Field(..., description="Tipo de mensaje")
    ack: Optional[MessageAck] = Field(None, description="Estado de confirmación")
    from_me: bool = Field(..., description="Mensaje enviado por mí")

    # Campos opcionales para diferentes tipos de mensaje
    caption: Optional[str] = Field(None, description="Descripción de media")
    filename: Optional[str] = Field(None, description="Nombre del archivo")
    mimetype: Optional[str] = Field(None, description="Tipo MIME")
    media_url: Optional[str] = Field(None, description="URL del archivo multimedia")

    # Información de ubicación
    latitude: Optional[float] = Field(None, description="Latitud")
    longitude: Optional[float] = Field(None, description="Longitud")

    # Información de contacto
    contact_name: Optional[str] = Field(
        None, description="Nombre del contacto compartido"
    )
    contact_phone: Optional[str] = Field(
        None, description="Teléfono del contacto compartido"
    )

    # Metadatos adicionales
    quoted_msg_id: Optional[str] = Field(None, description="ID del mensaje citado")
    forwarded: Optional[bool] = Field(False, description="Mensaje reenviado")

    model_config = ConfigDict(populate_by_name=True)


class MessageAckEvent(BaseModel):
    """Evento de confirmación de mensaje"""

    id: str = Field(..., description="ID del mensaje")
    ack: MessageAck = Field(..., description="Estado de confirmación")
    timestamp: int = Field(..., description="Timestamp de la confirmación")
    from_user: str = Field(..., alias="from", description="Remitente original")
    to: str = Field(..., description="Destinatario original")

    model_config = ConfigDict(populate_by_name=True)


class SessionStatusEvent(BaseModel):
    """Evento de cambio de estado de sesión"""

    session: str = Field(..., description="Nombre de la sesión")
    status: SessionStatus = Field(..., description="Nuevo estado de la sesión")
    timestamp: int = Field(..., description="Timestamp del cambio")
    qr: Optional[str] = Field(None, description="Código QR (si aplica)")

    model_config = ConfigDict(populate_by_name=True)


class PresenceUpdateEvent(BaseModel):
    """Evento de actualización de presencia"""

    id: str = Field(..., description="ID del contacto")
    presence: PresenceStatus = Field(..., description="Estado de presencia")
    timestamp: int = Field(..., description="Timestamp de la actualización")

    model_config = ConfigDict(populate_by_name=True)


class WebhookResponse(BaseModel):
    """Respuesta estándar para webhooks"""

    status: str = Field(..., description="Estado del procesamiento")
    message: str = Field(..., description="Mensaje descriptivo")
    event_type: Optional[str] = Field(None, description="Tipo de evento procesado")
    timestamp: str = Field(..., description="Timestamp de procesamiento")


class WebhookEventList(BaseModel):
    """Lista de eventos de webhook"""

    events: list[Dict[str, Any]] = Field(..., description="Lista de eventos")
    total: int = Field(..., description="Total de eventos")
    timestamp: str = Field(..., description="Timestamp de la consulta")


class WebhookConfig(BaseModel):
    """Configuración de webhook"""

    url: str = Field(..., description="URL del webhook")
    events: list[str] = Field(..., description="Tipos de eventos a enviar")
    enabled: bool = Field(True, description="Webhook habilitado")
    secret: Optional[str] = Field(None, description="Secreto para validación")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://mi-backend.com/api/v1/webhooks/waha",
                "events": ["message", "message.ack", "session.status"],
                "enabled": True,
                "secret": "mi-secreto-webhook",
            }
        }
    )
