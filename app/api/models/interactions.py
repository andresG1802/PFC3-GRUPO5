"""Modelos Pydantic para interactions"""

from pydantic import BaseModel, Field, ConfigDict, field_serializer
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
            "example": [{"route": "route_1", "step": 1, "userInput": "1"}]
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

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="_id", description="ID de la interaction")
    createdAt: datetime = Field(..., description="Fecha de creación")
    asesor_id: Optional[str] = Field(default=None, description="ID del asesor asignado")
    assignedAt: Optional[datetime] = Field(
        default=None, description="Fecha de asignación del asesor"
    )
    # Summary text generated from timeline entries and current route
    summary: Optional[str] = Field(
        default=None,
        description="Generated textual summary based on timeline and route",
    )

    @field_serializer("createdAt", "assignedAt", when_used="json")
    def _serialize_dt(self, v: datetime):
        return v.isoformat() if v is not None else None


class AssignAsesorResponse(BaseModel):
    """Modelo de respuesta para asignación de asesor"""

    model_config = ConfigDict()

    message: str
    interaction_id: str
    asesor_id: str
    assignedAt: datetime

    @field_serializer("assignedAt", when_used="json")
    def _serialize_assigned(self, v: datetime):
        return v.isoformat() if v is not None else None
