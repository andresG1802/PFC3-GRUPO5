"""Health - Endpoint básico de health check (mantenido por compatibilidad)"""

from fastapi import APIRouter
from datetime import datetime

# Importar modelos desde el módulo centralizado
from ..models.health import HealthResponse

# Configurar router con tags a nivel de clase
router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Endpoint básico de health check

    Returns:
        HealthResponse: Estado del servicio
    """
    return HealthResponse(
        status="healthy", timestamp=datetime.now(), service="backend-api"
    )
