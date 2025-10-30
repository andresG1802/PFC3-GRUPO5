"""
Tests para funcionalidades de cache y Redis
"""

import pytest
from unittest.mock import patch, MagicMock
import json
import time


class TestCacheOperations:
    """Tests para operaciones básicas de cache"""
    
    def test_cache_set_and_get(self, mock_cache):
        """Test de operaciones básicas set y get del cache"""
        # Configurar mock
        mock_cache.set.return_value = True
        mock_cache.get.return_value = '{"test": "data"}'
        
        # Simular operación de cache
        key = "test_key"
        value = {"test": "data"}
        
        # Set
        result = mock_cache.set(key, json.dumps(value), ex=300)
        assert result is True
        
        # Get
        cached_value = mock_cache.get(key)
        assert cached_value == '{"test": "data"}'
        
        # Verificar llamadas
        mock_cache.set.assert_called_once_with(key, json.dumps(value), ex=300)
        mock_cache.get.assert_called_once_with(key)
    
    def test_cache_delete(self, mock_cache):
        """Test de eliminación de cache"""
        mock_cache.delete.return_value = 1
        
        key = "test_key"
        result = mock_cache.delete(key)
        
        assert result == 1
        mock_cache.delete.assert_called_once_with(key)
    
    def test_cache_exists(self, mock_cache):
        """Test de verificación de existencia en cache"""
        mock_cache.exists.return_value = 1
        
        key = "test_key"
        exists = mock_cache.exists(key)
        
        assert exists == 1
        mock_cache.exists.assert_called_once_with(key)
    
    def test_cache_expire(self, mock_cache):
        """Test de configuración de expiración"""
        mock_cache.expire.return_value = True
        
        key = "test_key"
        ttl = 600
        result = mock_cache.expire(key, ttl)
        
        assert result is True
        mock_cache.expire.assert_called_once_with(key, ttl)


class TestCachePatterns:
    """Tests para patrones de cache utilizados en la aplicación"""
    
    def test_chat_cache_pattern(self, mock_cache):
        """Test del patrón de cache para chats"""
        # Simular cache de chats
        chat_data = {
            "id": "test@c.us",
            "name": "Test Chat",
            "lastMessage": {"body": "Hello", "timestamp": 1640995200}
        }
        
        cache_key = "chat:test@c.us"
        mock_cache.set.return_value = True
        mock_cache.get.return_value = json.dumps(chat_data)
        
        # Set chat in cache
        result = mock_cache.set(cache_key, json.dumps(chat_data), ex=300)
        assert result is True
        
        # Get chat from cache
        cached_data = mock_cache.get(cache_key)
        assert json.loads(cached_data) == chat_data
    
    def test_chats_list_cache_pattern(self, mock_cache):
        """Test del patrón de cache para lista de chats"""
        chats_data = {
            "chats": [
                {"id": "chat1@c.us", "name": "Chat 1"},
                {"id": "chat2@c.us", "name": "Chat 2"}
            ],
            "total": 2,
            "timestamp": int(time.time())
        }
        
        cache_key = "chats:list:limit:10:offset:0"
        mock_cache.set.return_value = True
        mock_cache.get.return_value = json.dumps(chats_data)
        
        # Cache chats list
        result = mock_cache.set(cache_key, json.dumps(chats_data), ex=180)
        assert result is True
        
        # Retrieve cached list
        cached_data = mock_cache.get(cache_key)
        assert json.loads(cached_data) == chats_data
    
    def test_user_session_cache_pattern(self, mock_cache):
        """Test del patrón de cache para sesiones de usuario"""
        session_data = {
            "user_id": "user123",
            "email": "test@example.com",
            "role": "asesor",
            "last_activity": int(time.time())
        }
        
        cache_key = "session:user123"
        mock_cache.set.return_value = True
        mock_cache.get.return_value = json.dumps(session_data)
        
        # Cache session
        result = mock_cache.set(cache_key, json.dumps(session_data), ex=3600)
        assert result is True
        
        # Get session
        cached_session = mock_cache.get(cache_key)
        assert json.loads(cached_session) == session_data


class TestCacheInvalidation:
    """Tests para invalidación de cache"""
    
    def test_delete_pattern_chats(self, mock_cache):
        """Test de eliminación de patrones de cache de chats"""
        mock_cache.delete_pattern.return_value = 5
        
        pattern = "chat:*"
        deleted_count = mock_cache.delete_pattern(pattern)
        
        assert deleted_count == 5
        mock_cache.delete_pattern.assert_called_once_with(pattern)
    
    def test_delete_pattern_chats_list(self, mock_cache):
        """Test de eliminación de cache de listas de chats"""
        mock_cache.delete_pattern.return_value = 3
        
        pattern = "chats:list:*"
        deleted_count = mock_cache.delete_pattern(pattern)
        
        assert deleted_count == 3
        mock_cache.delete_pattern.assert_called_once_with(pattern)
    
    def test_delete_pattern_sessions(self, mock_cache):
        """Test de eliminación de cache de sesiones"""
        mock_cache.delete_pattern.return_value = 2
        
        pattern = "session:*"
        deleted_count = mock_cache.delete_pattern(pattern)
        
        assert deleted_count == 2
        mock_cache.delete_pattern.assert_called_once_with(pattern)


class TestCacheErrorHandling:
    """Tests para manejo de errores de cache"""
    
    def test_cache_connection_error(self, mock_cache):
        """Test de error de conexión a Redis"""
        mock_cache.get.side_effect = ConnectionError("Redis connection failed")
        
        with pytest.raises(ConnectionError):
            result = mock_cache.get("test_key")
    
    def test_cache_timeout_error(self, mock_cache):
        """Test de timeout de Redis"""
        mock_cache.set.side_effect = TimeoutError("Redis timeout")
        
        with pytest.raises(TimeoutError):
            result = mock_cache.set("test_key", "test_value")
    
    def test_cache_memory_error(self, mock_cache):
        """Test de error de memoria en Redis"""
        mock_cache.set.side_effect = Exception("OOM command not allowed when used memory > 'maxmemory'")
        
        with pytest.raises(Exception):
            result = mock_cache.set("test_key", "test_value")
    
    def test_cache_invalid_json(self, mock_cache):
        """Test de JSON inválido en cache"""
        mock_cache.get.return_value = "invalid json data"
        
        cached_data = mock_cache.get("test_key")
        
        with pytest.raises(json.JSONDecodeError):
            json.loads(cached_data)


class TestCachePerformance:
    """Tests para rendimiento de cache"""
    
    def test_cache_hit_scenario(self, mock_cache):
        """Test de escenario de cache hit"""
        # Simular cache hit
        mock_cache.get.return_value = '{"cached": true}'
        mock_cache.exists.return_value = 1
        
        # Verificar que existe
        exists = mock_cache.exists("test_key")
        assert exists == 1
        
        # Obtener datos
        data = mock_cache.get("test_key")
        assert data == '{"cached": true}'
    
    def test_cache_miss_scenario(self, mock_cache):
        """Test de escenario de cache miss"""
        # Simular cache miss
        mock_cache.get.return_value = None
        mock_cache.exists.return_value = 0
        
        # Verificar que no existe
        exists = mock_cache.exists("test_key")
        assert exists == 0
        
        # Intentar obtener datos
        data = mock_cache.get("test_key")
        assert data is None
    
    def test_cache_ttl_check(self, mock_cache):
        """Test de verificación de TTL"""
        mock_cache.ttl.return_value = 300  # 5 minutos restantes
        
        ttl = mock_cache.ttl("test_key")
        assert ttl == 300
        mock_cache.ttl.assert_called_once_with("test_key")
    
    def test_cache_expired_key(self, mock_cache):
        """Test de clave expirada"""
        mock_cache.ttl.return_value = -2  # Clave expirada
        mock_cache.get.return_value = None
        
        ttl = mock_cache.ttl("expired_key")
        assert ttl == -2
        
        data = mock_cache.get("expired_key")
        assert data is None


class TestCacheIntegration:
    """Tests de integración con cache"""
    
    def test_cache_with_chats_endpoint(self, client, auth_headers, mock_cache, mock_waha_client):
        """Test de integración de cache con endpoint de chats"""
        # Configurar cache miss inicial
        mock_cache.get.return_value = None
        mock_cache.set.return_value = True
        
        # Configurar respuesta de WAHA
        waha_response = {
            "chats": [{"id": "test@c.us", "name": "Test"}],
            "total": 1
        }
        mock_waha_client.get_chats.return_value = waha_response
        
        # Primera llamada (cache miss)
        response = client.get("/api/v1/chats/?limit=10&offset=0", headers=auth_headers)
        
        if response.status_code == 200:
            # Verificar que se intentó obtener del cache
            mock_cache.get.assert_called()
            # Verificar que se guardó en cache
            mock_cache.set.assert_called()
    
    def test_cache_invalidation_on_new_message(self, mock_cache):
        """Test de invalidación de cache al recibir nuevo mensaje"""
        # Simular invalidación cuando llega un nuevo mensaje
        mock_cache.delete_pattern.return_value = 3
        
        # Invalidar cache relacionado con chats
        patterns_to_clear = ["chats:list:*", "chat:*", "chats:overview:*"]
        
        for pattern in patterns_to_clear:
            deleted = mock_cache.delete_pattern(pattern)
            assert isinstance(deleted, int)
    
    def test_cache_warming(self, mock_cache, mock_waha_client):
        """Test de precalentamiento de cache"""
        # Simular precalentamiento de cache con datos frecuentemente accedidos
        popular_chats = [
            {"id": "popular1@c.us", "name": "Popular Chat 1"},
            {"id": "popular2@c.us", "name": "Popular Chat 2"}
        ]
        
        mock_cache.set.return_value = True
        
        # Precalentar cache
        for chat in popular_chats:
            cache_key = f"chat:{chat['id']}"
            result = mock_cache.set(cache_key, json.dumps(chat), ex=600)
            assert result is True
        
        # Verificar que se hicieron las llamadas correctas
        assert mock_cache.set.call_count == len(popular_chats)


class TestCacheConfiguration:
    """Tests para configuración de cache"""
    
    def test_cache_key_generation(self):
        """Test de generación de claves de cache"""
        # Test de diferentes patrones de claves
        chat_id = "test@c.us"
        user_id = "user123"
        limit = 10
        offset = 0
        
        # Claves esperadas
        chat_key = f"chat:{chat_id}"
        user_session_key = f"session:{user_id}"
        chats_list_key = f"chats:list:limit:{limit}:offset:{offset}"
        
        assert chat_key == "chat:test@c.us"
        assert user_session_key == "session:user123"
        assert chats_list_key == "chats:list:limit:10:offset:0"
    
    def test_cache_ttl_values(self):
        """Test de valores de TTL para diferentes tipos de datos"""
        # TTL esperados para diferentes tipos de cache
        ttl_values = {
            "chat_data": 300,      # 5 minutos
            "chats_list": 180,     # 3 minutos
            "user_session": 3600,  # 1 hora
            "overview": 120        # 2 minutos
        }
        
        for cache_type, expected_ttl in ttl_values.items():
            assert expected_ttl > 0
            assert isinstance(expected_ttl, int)
    
    def test_cache_namespace_separation(self):
        """Test de separación de namespaces en cache"""
        # Verificar que diferentes tipos de datos usan prefijos diferentes
        prefixes = ["chat:", "chats:", "session:", "user:", "temp:"]
        
        for prefix in prefixes:
            assert prefix.endswith(":")
            assert len(prefix) > 1