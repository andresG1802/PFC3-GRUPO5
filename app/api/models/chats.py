"""
Modelos Pydantic para el router de Chats
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime
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
