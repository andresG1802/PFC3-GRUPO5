"""
Modelos Pydantic para el router de Interactions
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class TimelineEntry(BaseModel):
    """Modelo para entradas del timeline"""
    route: Optional[str] = None
    step: Optional[int] = None
    userInput: Optional[str] = None


class InteractionBase(BaseModel):
    """Modelo base para interaction"""
    phone: str = Field(..., description="Número de teléfono")
    state: str = Field(default="menus", description="Estado actual")
    route: str = Field(..., description="Ruta actual")
    step: int = Field(default=1, description="Paso actual")
    lang: Optional[str] = Field(default=None, description="Idioma")
    timeline: List[TimelineEntry] = Field(default_factory=list, description="Historial de interacciones")


class InteractionCreate(InteractionBase):
    """Modelo para crear interaction"""
    pass


class InteractionUpdate(BaseModel):
    """Modelo para actualizar interaction"""
    state: Optional[str] = None
    route: Optional[str] = None
    step: Optional[int] = None
    lang: Optional[str] = None
    timeline: Optional[List[TimelineEntry]] = None


class InteractionResponse(InteractionBase):
    """Modelo de respuesta para interaction"""
    id: str = Field(..., alias="_id", description="ID de la interaction")
    createdAt: datetime = Field(..., description="Fecha de creación")

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class InteractionListResponse(BaseModel):
    """Modelo de respuesta para lista de interactions"""
    interactions: List[InteractionResponse]
    total: int
    skip: int
    limit: int