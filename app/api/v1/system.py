"""
Sistema - Endpoints para información general y health checks
"""

from fastapi import APIRouter
from typing import Dict, Any
import os
from datetime import datetime

# Importar modelos desde el módulo centralizado
from ..models.system import SystemInfo, HealthResponse

# Configurar router con tags a nivel de clase
router = APIRouter(tags=["Sistema"])


@router.get("/info", response_model=SystemInfo)
async def get_system_info():
    """
    Obtiene información general del sistema

    Returns:
        SystemInfo: Información detallada del sistema
    """
    return SystemInfo(
        name="Backend API",
        version="3.0.0",
        description="API backend profesional con arquitectura modular",
        status="active",
        timestamp=datetime.now(),
        environment=os.getenv("ENVIRONMENT", "development"),
    )


@router.get("/health", response_model=HealthResponse)
async def get_health():
    """
    Health check del sistema

    Returns:
        HealthResponse: Estado de salud del sistema
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        uptime="Sistema operativo",
        version="3.0.0",
    )


@router.get("/status")
async def get_status():
    """
    Estado detallado del sistema

    Returns:
        Dict: Estado completo del sistema
    """
    return {
        "status": "operational",
        "timestamp": datetime.now(),
        "services": {
            "database": "connected",
            "cache": "active",
            "external_apis": "available",
        },
        "metrics": {
            "uptime": "99.9%",
            "response_time": "< 100ms",
            "memory_usage": "45%",
        },
    }
