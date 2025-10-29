"""
Sistema de cache usando Redis para mejorar rendimiento
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, Union
import hashlib
import asyncio
import inspect
from functools import wraps

import redis
from redis.exceptions import ConnectionError, TimeoutError, RedisError

logger = logging.getLogger(__name__)


class RedisCache:
    """Cache usando Redis con TTL y estadísticas"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        default_ttl: int = 300,
        key_prefix: str = "afapa:cache:",
    ):
        """
        Inicializa el cache Redis

        Args:
            host: Host de Redis
            port: Puerto de Redis
            db: Base de datos de Redis
            password: Contraseña de Redis (opcional)
            default_ttl: TTL por defecto en segundos
            key_prefix: Prefijo para las claves
        """
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix

        # Configurar conexión Redis
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )

        # Estadísticas locales (se resetean al reiniciar)
        self._hits = 0
        self._misses = 0

        # Verificar conexión
        try:
            self.redis_client.ping()
            logger.info(
                f"Cache Redis inicializado - host: {host}:{port}, db: {db}, default_ttl: {default_ttl}s"
            )
        except Exception as e:
            logger.error(f"Error conectando a Redis: {e}")
            raise ConnectionError(f"No se pudo conectar a Redis: {e}")

    def _generate_key(self, key: Union[str, Dict[str, Any]]) -> str:
        """
        Genera una clave de cache consistente con prefijo

        Args:
            key: Clave original (string o dict)

        Returns:
            Clave de cache normalizada con prefijo
        """
        if isinstance(key, dict):
            # Convertir dict a string ordenado para consistencia
            sorted_items = sorted(key.items())
            key_str = json.dumps(sorted_items, sort_keys=True)
        else:
            key_str = str(key)

        # Usar hash para claves muy largas
        if len(key_str) > 100:
            key_str = hashlib.md5(key_str.encode()).hexdigest()

        return f"{self.key_prefix}{key_str}"

    def get(self, key: Union[str, Dict[str, Any]]) -> Optional[Any]:
        """
        Obtiene un valor del cache

        Args:
            key: Clave del cache

        Returns:
            Valor del cache o None si no existe/expiró
        """
        cache_key = self._generate_key(key)

        try:
            value = self.redis_client.get(cache_key)

            if value is None:
                self._misses += 1
                logger.debug(f"Cache miss: {cache_key}")
                return None

            # Deserializar el valor JSON
            try:
                deserialized_value = json.loads(value)
                self._hits += 1
                logger.debug(f"Cache hit: {cache_key}")
                return deserialized_value
            except json.JSONDecodeError as e:
                logger.warning(f"Error deserializando cache {cache_key}: {e}")
                self.delete(key)  # Limpiar entrada corrupta
                self._misses += 1
                return None

        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.error(f"Error accediendo a Redis: {e}")
            self._misses += 1
            return None

    def set(
        self, key: Union[str, Dict[str, Any]], value: Any, ttl: Optional[int] = None
    ) -> bool:
        """
        Establece un valor en el cache

        Args:
            key: Clave del cache
            value: Valor a almacenar
            ttl: TTL en segundos (usa default_ttl si es None)

        Returns:
            True si se guardó exitosamente, False en caso contrario
        """
        cache_key = self._generate_key(key)
        ttl = ttl if ttl is not None else self.default_ttl

        try:
            # Serializar el valor a JSON
            serialized_value = json.dumps(value, default=str)

            # Guardar en Redis con TTL
            if ttl > 0:
                result = self.redis_client.setex(cache_key, ttl, serialized_value)
            else:
                result = self.redis_client.set(cache_key, serialized_value)

            if result:
                logger.debug(f"Cache set: {cache_key} (TTL: {ttl}s)")
                return True
            else:
                logger.warning(f"Error guardando en cache: {cache_key}")
                return False

        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.error(f"Error guardando en Redis: {e}")
            return False
        except (TypeError, ValueError) as e:
            logger.error(f"Error serializando valor para cache {cache_key}: {e}")
            return False

    def delete(self, key: Union[str, Dict[str, Any]]) -> bool:
        """
        Elimina una entrada del cache

        Args:
            key: Clave a eliminar

        Returns:
            True si se eliminó, False si no existía o hubo error
        """
        cache_key = self._generate_key(key)

        try:
            result = self.redis_client.delete(cache_key)
            if result > 0:
                logger.debug(f"Cache delete: {cache_key}")
                return True
            return False
        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.error(f"Error eliminando de Redis: {e}")
            return False

    def clear(self) -> int:
        """
        Limpia todas las entradas del cache con el prefijo

        Returns:
            Número de entradas eliminadas
        """
        try:
            # Buscar todas las claves con nuestro prefijo
            pattern = f"{self.key_prefix}*"
            keys = self.redis_client.keys(pattern)

            if keys:
                count = self.redis_client.delete(*keys)
                logger.info(f"Cache cleared: {count} entradas eliminadas")
                return count
            else:
                logger.info("Cache cleared: 0 entradas encontradas")
                return 0

        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.error(f"Error limpiando cache Redis: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del cache

        Returns:
            Dict con estadísticas del cache
        """
        try:
            # Obtener info de Redis
            redis_info = self.redis_client.info()

            # Contar claves con nuestro prefijo
            pattern = f"{self.key_prefix}*"
            total_entries = len(self.redis_client.keys(pattern))

            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests) if total_requests > 0 else 0

            return {
                "total_entries": total_entries,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "default_ttl": self.default_ttl,
                "redis_memory_usage": redis_info.get("used_memory_human", "N/A"),
                "redis_connected_clients": redis_info.get("connected_clients", 0),
                "redis_uptime": redis_info.get("uptime_in_seconds", 0),
            }
        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.error(f"Error obteniendo estadísticas de Redis: {e}")
            return {
                "total_entries": 0,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": 0,
                "default_ttl": self.default_ttl,
                "error": str(e),
            }

    def get_keys(self) -> list:
        """Obtiene todas las claves del cache"""
        try:
            pattern = f"{self.key_prefix}*"
            keys = self.redis_client.keys(pattern)
            # Remover el prefijo para devolver claves limpias
            return [key.replace(self.key_prefix, "") for key in keys]
        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.error(f"Error obteniendo claves de Redis: {e}")
            return []

    def ping(self) -> bool:
        """Verifica la conexión con Redis"""
        try:
            return self.redis_client.ping()
        except Exception:
            return False


# Instancia global del cache
_global_cache: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    """
    Obtiene la instancia global del cache Redis

    Returns:
        Instancia del cache Redis
    """
    global _global_cache

    if _global_cache is None:
        # Obtener configuración desde variables de entorno
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))
        redis_password = os.getenv("REDIS_PASSWORD")

        _global_cache = RedisCache(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            default_ttl=300,  # 5 minutos por defecto
            key_prefix="afapa:cache:",
        )

    return _global_cache


def cache_key_for_chats(limit: int, offset: int, filters: Optional[Dict] = None) -> str:
    """
    Genera clave de cache para lista de chats

    Args:
        limit: Límite de resultados
        offset: Desplazamiento
        filters: Filtros opcionales

    Returns:
        Clave de cache como string
    """
    return f"chats:{limit}:{offset}"


def cache_key_for_chat(chat_id: str) -> str:
    """
    Genera clave de cache para chat específico

    Args:
        chat_id: ID del chat

    Returns:
        Clave de cache como string
    """
    return f"chat:{chat_id}"


def cache_key_for_overview(limit: int, offset: int) -> str:
    """
    Genera clave de cache para overview de chats

    Args:
        limit: Límite de resultados
        offset: Desplazamiento

    Returns:
        Clave de cache como string
    """
    return f"overview:{limit}:{offset}"


# Decorador para cache automático
def cached(ttl: int = 300, key_func: Optional[callable] = None):
    """
    Decorador para cache automático de funciones

    Args:
        ttl: TTL en segundos
        key_func: Función para generar la clave (usa args por defecto)
    """

    def decorator(func):
        is_async = inspect.iscoroutinefunction(func)

        if is_async:

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                cache = get_cache()

                # Generar clave
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = {
                        "func": func.__name__,
                        "args": str(args),
                        "kwargs": str(sorted(kwargs.items())),
                    }

                # Intentar obtener del cache
                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    return cached_result

                # Ejecutar función y cachear resultado
                result = await func(*args, **kwargs)
                cache.set(cache_key, result, ttl)

                return result

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                cache = get_cache()

                # Generar clave
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = {
                        "func": func.__name__,
                        "args": str(args),
                        "kwargs": str(sorted(kwargs.items())),
                    }

                # Intentar obtener del cache
                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    return cached_result

                # Ejecutar función y cachear resultado
                result = func(*args, **kwargs)
                cache.set(cache_key, result, ttl)

                return result

            return sync_wrapper

    return decorator
