"""
Configuración global de pytest y fixtures compartidos
"""

import asyncio
import os
import sys
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Cargar variables de entorno de test antes de importar la app
test_env_path = os.path.join(os.path.dirname(__file__), ".env.test")
load_dotenv(test_env_path, override=True)

# Agregar el directorio padre al path para importar la app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock de servicios externos antes de importar la app
with (
    patch("redis.Redis") as mock_redis,
    patch("pymongo.MongoClient") as mock_mongo,
    patch("app.services.cache.get_cache") as mock_get_cache,
    patch("app.services.waha_client.get_waha_client") as mock_get_waha,
    patch("app.database.models.AsesorModel") as mock_asesor_model,
):

    # Mock del cache Redis
    mock_cache_instance = MagicMock()
    mock_cache_instance.get.return_value = None
    mock_cache_instance.set.return_value = True
    mock_cache_instance.delete.return_value = 1
    mock_cache_instance.exists.return_value = 0
    mock_cache_instance.expire.return_value = True
    mock_cache_instance.ttl.return_value = -1
    mock_cache_instance.delete_pattern.return_value = 0
    mock_cache_instance.clear_pattern.return_value = 2
    mock_cache_instance.ping.return_value = True
    mock_get_cache.return_value = mock_cache_instance

    mock_waha_instance = MagicMock()
    mock_waha_instance.get_chats = AsyncMock(return_value=[])
    mock_waha_instance.get_chat_by_id = AsyncMock(return_value=None)
    mock_waha_instance.get_messages = AsyncMock(
        return_value={"messages": [], "total": 0}
    )
    mock_waha_instance.send_message = AsyncMock(
        return_value={"id": "test_msg", "status": "sent"}
    )
    mock_waha_instance.get_session_status = AsyncMock(
        return_value={"name": "default", "status": "WORKING"}
    )
    mock_waha_instance.close = AsyncMock()
    mock_waha_instance._normalize_chat_data = MagicMock(
        return_value={
            "id": "test@c.us",
            "name": "Test Chat",
            "type": "individual",
            "timestamp": None,
            "unread_count": 0,
            "archived": False,
            "pinned": False,
            "muted": False,
            "contact": None,
            "last_message": None,
            "picture_url": None,
        }
    )
    mock_get_waha.return_value = mock_waha_instance

    # Configurar mock de AsesorModel
    test_asesor = {
        "_id": "507f1f77bcf86cd799439011",
        "email": "test@example.com",
        "password": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",  # "password" hasheado
        "full_name": "Test User",
        "role": "asesor",
        "is_active": True,
    }

    test_admin = {
        "_id": "507f1f77bcf86cd799439012",
        "email": "admin@example.com",
        "password": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",  # "password" hasheado
        "full_name": "Test Admin",
        "role": "admin",
        "is_active": True,
    }

    mock_asesor_model.find_by_email.side_effect = lambda email: {
        "test@example.com": test_asesor,
        "admin@example.com": test_admin,
    }.get(email)

    mock_asesor_model.create_asesor.return_value = "507f1f77bcf86cd799439013"

    from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Crea un event loop para toda la sesión de tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Cliente de prueba para FastAPI"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Cliente asíncrono para pruebas"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_waha_client():
    """Mock del cliente WAHA para tests"""
    mock = MagicMock()

    # Configurar métodos básicos
    mock.get_chats = AsyncMock(return_value=[])
    mock.get_chat_by_id = AsyncMock(return_value=None)
    mock.get_messages = AsyncMock(return_value={"messages": [], "total": 0})
    mock.send_message = AsyncMock(return_value={"id": "test_msg", "status": "sent"})
    mock.get_session_status = AsyncMock(return_value={"status": "ready"})
    mock.close = AsyncMock()
    mock._normalize_chat_data = MagicMock(
        return_value={
            "id": "test@c.us",
            "name": "Test Chat",
            "type": "individual",
            "timestamp": None,
            "unread_count": 0,
            "archived": False,
            "pinned": False,
            "muted": False,
            "contact": None,
            "last_message": None,
            "picture_url": None,
        }
    )

    return mock


@pytest.fixture
def mock_cache():
    """Mock del servicio de cache Redis"""
    mock_cache = MagicMock()

    # Configurar métodos básicos
    mock_cache.get.return_value = None
    mock_cache.set.return_value = True
    mock_cache.delete.return_value = 1
    mock_cache.exists.return_value = 0
    mock_cache.expire.return_value = True
    mock_cache.ttl.return_value = -1
    mock_cache.delete_pattern.return_value = 0
    mock_cache.clear_pattern.return_value = 2
    mock_cache.ping.return_value = True

    return mock_cache


@pytest.fixture
def mock_asesor_model():
    """Mock del modelo de Asesor - ya configurado globalmente"""
    # El mock ya está configurado globalmente, solo retornamos None
    return None


@pytest.fixture
def valid_jwt_token():
    """Token JWT válido para pruebas"""
    from datetime import timedelta

    from app.api.v1.auth import create_access_token

    token = create_access_token(
        data={"sub": "test@example.com", "role": "asesor"},
        expires_delta=timedelta(minutes=30),
    )
    return token


@pytest.fixture
def admin_jwt_token():
    """Token JWT de administrador para pruebas"""
    from datetime import timedelta

    from app.api.v1.auth import create_access_token

    token = create_access_token(
        data={"sub": "admin@example.com", "role": "admin"},
        expires_delta=timedelta(minutes=30),
    )
    return token


@pytest.fixture
def auth_headers(valid_jwt_token):
    """Headers de autenticación para pruebas"""
    return {"Authorization": f"Bearer {valid_jwt_token}"}


@pytest.fixture
def admin_auth_headers(admin_jwt_token):
    """Headers de autenticación de administrador para pruebas"""
    return {"Authorization": f"Bearer {admin_jwt_token}"}


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Configuración automática del entorno de pruebas"""
    # Los mocks ya están aplicados globalmente
    yield
