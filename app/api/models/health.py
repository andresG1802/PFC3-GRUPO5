"""
Modelos Pydantic para el router de Health
"""

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Modelo para respuesta de health check"""

    status: str
    timestamp: datetime
    service: str
