"""
Modelos Pydantic para gestión de presencia de contactos
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List

from .webhooks import PresenceStatus


class PresenceInfo(BaseModel):
    """Información de presencia de un contacto"""

    contact_id: str = Field(..., description="ID del contacto")
    presence: str = Field(..., description="Estado de presencia actual")
    last_seen: Optional[int] = Field(None, description="Timestamp de última conexión")
    cached: bool = Field(False, description="Datos obtenidos desde cache")


class PresenceListResponse(BaseModel):
    """Respuesta con lista de presencias"""

    presences: List[PresenceInfo] = Field(..., description="Lista de presencias")
    total: int = Field(..., description="Total de presencias")
    timestamp: str = Field(..., description="Timestamp de la consulta")


class PresenceResponse(BaseModel):
    """Respuesta con información de presencia individual"""

    presence: PresenceInfo = Field(..., description="Información de presencia")
    timestamp: str = Field(..., description="Timestamp de la consulta")


class PresenceUpdateRequest(BaseModel):
    """Solicitud para actualizar presencia propia"""

    presence: PresenceStatus = Field(..., description="Nuevo estado de presencia")

    model_config = ConfigDict(json_schema_extra={"example": {"presence": "online"}})
