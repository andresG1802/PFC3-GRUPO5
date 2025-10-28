"""
Modelos Pydantic para el router de Interactions
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class InteractionState(str, Enum):
    """Estados posibles para una interaction"""

    MENUS = "menus"
    PENDING = "pending"
    DERIVED = "derived"
    CLOSED = "closed"


class TimelineEntry(BaseModel):
    """Modelo para entradas del timeline"""

    route: Optional[str] = None
    step: Optional[int] = None
    userInput: Optional[str] = None


class InteractionBase(BaseModel):
    """Modelo base para interaction"""

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
        # {"route_1", "1", "1"}
        # {[ruta anterior], [step anterior], [input del usuario anterior]}
    )


class InteractionUpdate(BaseModel):
    """Modelo para actualizar interaction"""

    state: Optional[InteractionState] = None
    route: Optional[str] = None  # route_1, route_2, ... , route_4
    step: Optional[int] = None  # 1, 2, 3, 4, 5
    lang: Optional[str] = None  # es, qu
    timeline: Optional[List[TimelineEntry]] = None


class InteractionResponse(InteractionBase):
    """Modelo de respuesta para interaction"""

    id: str = Field(..., alias="_id", description="ID de la interaction")
    createdAt: datetime = Field(..., description="Fecha de creación")
    asesor_id: Optional[str] = Field(default=None, description="ID del asesor asignado")
    assignedAt: Optional[datetime] = Field(
        default=None, description="Fecha de asignación del asesor"
    )

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}


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

    message: str
    interaction_id: str
    asesor_id: str
    assignedAt: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
