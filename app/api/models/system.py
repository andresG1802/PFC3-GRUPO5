"""
Modelos Pydantic para el router de Sistema
"""

from pydantic import BaseModel
from datetime import datetime


class SystemInfo(BaseModel):
    """Modelo para información del sistema"""

    name: str
    version: str
    description: str
    status: str
    timestamp: datetime
    environment: str


class HealthResponse(BaseModel):
    """Modelo para respuesta de health check"""

    status: str
    timestamp: datetime
    uptime: str
    version: str
