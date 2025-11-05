"""
Modelos Pydantic para el router de Chats
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Any, Dict
from enum import Enum


class ChatType(str, Enum):
    """Tipos de chat en WhatsApp"""

    INDIVIDUAL = "individual"
    GROUP = "group"
    BROADCAST = "broadcast"


class MessageType(str, Enum):
    """Tipos de mensaje en WhatsApp"""

    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    STICKER = "sticker"
    LOCATION = "location"
    CONTACT = "contact"
    VOICE = "voice"


class MessageAck(str, Enum):
    """Estados de confirmación de mensaje"""

    ERROR = "ERROR"
    PENDING = "PENDING"
    SERVER = "SERVER"
    DEVICE = "DEVICE"
    READ = "READ"
    PLAYED = "PLAYED"


class ContactInfo(BaseModel):
    """Información de contacto"""

    id: str = Field(..., description="ID del contacto")
    name: Optional[str] = Field(None, description="Nombre del contacto")
    pushname: Optional[str] = Field(None, description="Nombre push del contacto")
    short_name: Optional[str] = Field(None, description="Nombre corto")
    is_business: Optional[bool] = Field(False, description="Es cuenta de negocio")
    is_enterprise: Optional[bool] = Field(False, description="Es cuenta empresarial")


class LastMessage(BaseModel):
    """Último mensaje del chat"""

    id: str = Field(..., description="ID del mensaje")
    timestamp: int = Field(..., description="Timestamp del mensaje")
    from_me: bool = Field(..., description="Mensaje enviado por mí")
    type: MessageType = Field(..., description="Tipo de mensaje")
    body: Optional[str] = Field(None, description="Contenido del mensaje")
    ack: Optional[MessageAck] = Field(None, description="Estado de confirmación")


class ChatBase(BaseModel):
    """Modelo base para chat"""

    id: str = Field(..., description="ID único del chat")
    name: Optional[str] = Field(None, description="Nombre del chat")
    type: ChatType = Field(..., description="Tipo de chat")
    timestamp: Optional[int] = Field(None, description="Timestamp de última actividad")
    unread_count: Optional[int] = Field(0, description="Número de mensajes no leídos")
    archived: Optional[bool] = Field(False, description="Chat archivado")
    pinned: Optional[bool] = Field(False, description="Chat fijado")
    muted: Optional[bool] = Field(False, description="Chat silenciado")


class Chat(ChatBase):
    """Modelo completo para chat"""

    contact: Optional[ContactInfo] = Field(None, description="Información del contacto")
    last_message: Optional[LastMessage] = Field(None, description="Último mensaje")
    participants: Optional[List[ContactInfo]] = Field(
        None, description="Participantes del grupo"
    )
    group_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Metadatos del grupo"
    )
    picture_url: Optional[str] = Field(None, description="URL de la imagen del chat")


class ChatOverview(BaseModel):
    """Modelo para vista general de chats (optimizado para listas)"""

    id: str = Field(..., description="ID único del chat")
    name: Optional[str] = Field(None, description="Nombre del chat")
    type: ChatType = Field(..., description="Tipo de chat")
    timestamp: Optional[int] = Field(None, description="Timestamp de última actividad")
    unread_count: Optional[int] = Field(0, description="Número de mensajes no leídos")
    last_message: Optional[LastMessage] = Field(None, description="Último mensaje")
    picture_url: Optional[str] = Field(None, description="URL de la imagen del chat")
    archived: Optional[bool] = Field(False, description="Chat archivado")
    pinned: Optional[bool] = Field(False, description="Chat fijado")


class ChatListResponse(BaseModel):
    """Respuesta para lista de chats con paginación"""

    chats: List[ChatOverview] = Field(..., description="Lista de chats")
    total: int = Field(..., description="Total de chats disponibles")
    limit: int = Field(..., description="Límite aplicado")
    offset: int = Field(..., description="Desplazamiento aplicado")
    has_more: bool = Field(..., description="Hay más chats disponibles")


class ChatResponse(BaseModel):
    """Respuesta para un chat específico"""

    chat: Chat = Field(..., description="Información completa del chat")
    success: bool = Field(True, description="Operación exitosa")
    message: str = Field(
        "Chat obtenido exitosamente", description="Mensaje de respuesta"
    )


class Message(BaseModel):
    """Modelo para mensaje individual"""

    id: str = Field(..., description="ID único del mensaje")
    body: Optional[str] = Field(None, description="Contenido del mensaje")
    timestamp: int = Field(..., description="Timestamp del mensaje")
    from_me: bool = Field(..., description="Mensaje enviado por mí")
    type: MessageType = Field(..., description="Tipo de mensaje")
    from_contact: Optional[str] = Field(
        None, description="ID del contacto remitente", alias="from"
    )
    ack: Optional[MessageAck] = Field(None, description="Estado de confirmación")


class MessagesListResponse(BaseModel):
    """Respuesta para lista de mensajes con paginación"""

    messages: List[Message] = Field(..., description="Lista de mensajes")
    total: int = Field(..., description="Total de mensajes disponibles")
    limit: int = Field(..., description="Límite aplicado")
    offset: int = Field(..., description="Desplazamiento aplicado")


class SendMessageRequest(BaseModel):
    """Solicitud para enviar mensaje"""

    message: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Contenido del mensaje",
    )
    type: MessageType = Field(MessageType.TEXT, description="Tipo de mensaje")

    # Campos opcionales para metadatos
    reply_to: Optional[str] = Field(
        None, description="ID del mensaje al que se responde"
    )

    # Para mensajes de ubicación
    latitude: Optional[float] = Field(
        None, ge=-90, le=90, description="Latitud para mensajes de ubicación"
    )
    longitude: Optional[float] = Field(
        None, ge=-180, le=180, description="Longitud para mensajes de ubicación"
    )

    # Para mensajes multimedia
    media_url: Optional[str] = Field(
        None,
        description="URL del archivo multimedia",
    )
    filename: Optional[str] = Field(
        None,
        max_length=255,
        description="Nombre del archivo para documentos",
    )
    caption: Optional[str] = Field(
        None,
        max_length=1024,
        description="Descripción para archivos multimedia",
    )

    # Metadatos adicionales
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Metadatos adicionales del mensaje"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"message": "Hola, ¿cómo estás?", "type": "text"},
                {
                    "message": "Aquí tienes la imagen",
                    "type": "image",
                    "media_url": "https://example.com/image.jpg",
                    "caption": "Imagen del producto",
                },
                {
                    "message": "Mi ubicación actual",
                    "type": "location",
                    "latitude": -34.6037,
                    "longitude": -58.3816,
                },
            ]
        }
    )

    @field_validator("latitude", "longitude")
    @classmethod
    def validate_location_fields(cls, v, info):
        """Valida que los campos de ubicación estén completos"""
        if info.data.get("type") == MessageType.LOCATION:
            if info.field_name == "latitude" and v is None:
                raise ValueError("Los mensajes de ubicación requieren latitud")
            if info.field_name == "longitude" and v is None:
                raise ValueError("Los mensajes de ubicación requieren longitud")
        return v

    @field_validator("media_url")
    @classmethod
    def validate_media_url(cls, v, info):
        """Valida que media_url esté presente para mensajes multimedia"""
        message_type = info.data.get("type")
        if message_type in [
            MessageType.IMAGE,
            MessageType.VIDEO,
            MessageType.AUDIO,
            MessageType.DOCUMENT,
        ]:
            if not v:
                raise ValueError(
                    f"Los mensajes de tipo {message_type} requieren media_url"
                )
        return v

    @field_validator("message")
    @classmethod
    def validate_message_content(cls, v, info):
        """Valida el contenido del mensaje según el tipo"""
        message_type = info.data.get("type", MessageType.TEXT)

        # Para mensajes de texto, validar que no esté vacío después de strip
        if message_type == MessageType.TEXT:
            if not v or not v.strip():
                raise ValueError("El contenido del mensaje no puede estar vacío")

        # Para mensajes de ubicación, el mensaje puede ser opcional
        if message_type == MessageType.LOCATION and not v:
            return "Ubicación compartida"

        return v.strip() if v else v


class SendMessageResponse(BaseModel):
    """Respuesta para envío de mensaje"""

    id: str = Field(..., description="ID del mensaje enviado")
    status: str = Field(..., description="Estado del envío")
    timestamp: int = Field(..., description="Timestamp del envío")


class ErrorResponse(BaseModel):
    """Respuesta de error estándar"""

    success: bool = Field(False, description="Operación fallida")
    error: str = Field(..., description="Tipo de error")
    message: str = Field(..., description="Mensaje de error")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Detalles adicionales del error"
    )


class WAHASessionInfo(BaseModel):
    """Información de sesión de WAHA"""

    name: str = Field(..., description="Nombre de la sesión")
    status: str = Field(..., description="Estado de la sesión")
    config: Optional[Dict[str, Any]] = Field(
        None, description="Configuración de la sesión"
    )


class ChatFilters(BaseModel):
    """Filtros para búsqueda de chats"""

    archived: Optional[bool] = Field(None, description="Filtrar por chats archivados")
    unread_only: Optional[bool] = Field(None, description="Solo chats no leídos")
    chat_type: Optional[ChatType] = Field(None, description="Filtrar por tipo de chat")
    search_term: Optional[str] = Field(
        None, description="Término de búsqueda en nombre"
    )
