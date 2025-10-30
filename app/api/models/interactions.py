"""Modelos Pydantic para interactions"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum


class InteractionState(str, Enum):
    """Estados posibles de una interaction"""

    MENUS = "menus"
    PENDING = "pending"
    DERIVED = "derived"
    CLOSED = "closed"


class TimelineEntry(BaseModel):
    """Entrada del timeline de una interaction"""

    timestamp: datetime = Field(..., description="Timestamp de la entrada")
    route: Optional[str] = None
    step: Optional[int] = None
    userInput: Optional[str] = None


class InteractionBase(BaseModel):
    """Modelo base para interaction"""

    chat_id: str = Field(..., description="ID del chat")
    phone: str = Field(..., description="Número de teléfono")
    state: InteractionState = Field(
        default=InteractionState.MENUS, description="Estado actual"
    )
    route: str = Field(..., description="Ruta actual")
    step: int = Field(default=1, description="Paso actual")
    lang: Optional[str] = Field(default=None, description="Idioma")
    timeline: List[TimelineEntry] = Field(
        default_factory=list,
        description="Historial de interacciones",
        json_schema_extra={
            "example": [
                {"timestamp": "2023-01-01T00:00:00", "route": "route_1", "step": 1}
            ]
        },
    )


class InteractionCreate(BaseModel):
    """Modelo para crear una nueva interaction"""

    chat_id: str = Field(..., description="ID del chat")
    phone: str = Field(..., description="Número de teléfono", pattern=r"^\+\d{10,15}$")
    state: InteractionState = Field(
        default=InteractionState.MENUS, description="Estado inicial"
    )
    route: str = Field(..., description="Ruta inicial")
    step: int = Field(default=1, description="Paso inicial")
    lang: Optional[str] = Field(default="es", description="Idioma (es, qu)")


class InteractionUpdate(BaseModel):
    """Modelo para actualizar una interaction"""

    state: Optional[InteractionState] = None
    route: Optional[str] = None  # route_1, route_2, ... , route_4
    step: Optional[int] = None  # 1, 2, 3, 4, 5
    lang: Optional[str] = None  # es, qu
    timeline: Optional[List[TimelineEntry]] = None


class InteractionResponse(InteractionBase):
    """Modelo de respuesta para interaction"""

    model_config = ConfigDict(
        populate_by_name=True, json_encoders={datetime: lambda v: v.isoformat()}
    )

    id: str = Field(..., alias="_id", description="ID de la interaction")
    createdAt: datetime = Field(..., description="Fecha de creación")
    asesor_id: Optional[str] = Field(default=None, description="ID del asesor asignado")
    assignedAt: Optional[datetime] = Field(
        default=None, description="Fecha de asignación del asesor"
    )


class InteractionListResponse(BaseModel):
    """Modelo de respuesta para lista de interactions con metadatos de paginación"""

    interactions: List[InteractionResponse]
    total: int = Field(
        ..., description="Número total de registros que coinciden con el filtro"
    )
    count: int = Field(..., description="Número de registros en la página actual")
    skip: int = Field(..., description="Número de registros omitidos")
    limit: int = Field(..., description="Límite de registros por página")
    has_next: bool = Field(..., description="Indica si hay más páginas disponibles")
    has_previous: bool = Field(..., description="Indica si hay páginas anteriores")
    page: int = Field(..., description="Número de página actual (basado en skip/limit)")
    total_pages: int = Field(..., description="Número total de páginas")


class AssignAsesorResponse(BaseModel):
    """Modelo de respuesta para asignación de asesor"""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    message: str
    interaction_id: str
    asesor_id: str
    assignedAt: datetime
