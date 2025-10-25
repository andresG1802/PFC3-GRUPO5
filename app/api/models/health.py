"""
Modelos Pydantic para el router de Health
"""

from pydantic import BaseModel
from datetime import datetime


class HealthResponse(BaseModel):
    """Modelo para respuesta de health check"""

    status: str
    timestamp: datetime
    service: str
