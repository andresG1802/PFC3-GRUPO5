"""
Middleware de rate limiting robusto con Redis para FastAPI
"""

import hashlib
import json
import logging
import time
from typing import Dict, Optional, Tuple

import redis.asyncio as redis
from fastapi import HTTPException, Request, Response
from fastapi.security.utils import get_authorization_scheme_param
from starlette.middleware.base import BaseHTTPMiddleware

from ..api.v1.auth import verify_token
from ..config.security import rate_limit_config

logger = logging.getLogger(__name__)


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Middleware de rate limiting con Redis que proporciona:
    - Límites por IP y usuario autenticado
    - Configuración diferenciada por endpoint
    - Bloqueo temporal por abuso
    - Logging y métricas
    - Configuración ajustable sin redeploy
    """

    def __init__(self, app):
        super().__init__(app)
        self.config = rate_limit_config
        self.redis_client: Optional[redis.Redis] = None
        self.redis_available = True

        logger.info(
            f"RateLimitingMiddleware inicializado - Enabled: {self.config.enabled}"
        )

    async def _init_redis(self):
        """Inicializa la conexión a Redis de forma asíncrona"""
        if not self.config.enabled:
            return

        try:
            self.redis_client = redis.from_url(
                self.config.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )

            # Verificar conexión
            await self.redis_client.ping()
            self.redis_available = True
            logger.info("Conexión a Redis establecida exitosamente")

        except Exception as e:
            self.redis_available = False
            logger.error(f"Error conectando a Redis: {e}")
            logger.warning(
                "Rate limiting funcionará en modo degradado (sin persistencia)"
            )

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Procesa la request aplicando rate limiting
        """
        # Si rate limiting está deshabilitado, continuar
        if not self.config.enabled:
            return await call_next(request)

        # Inicializar Redis si no está disponible
        if self.redis_client is None:
            await self._init_redis()

        try:
            # Obtener identificador del cliente
            client_id, is_authenticated = await self._get_client_identifier(request)

            # Obtener límites para el endpoint
            endpoint_key = f"{request.method} {request.url.path}"
            limits = self.config.get_endpoint_limits(request.method, request.url.path)

            # Aplicar multiplicador para usuarios autenticados
            if is_authenticated:
                limits["rpm"] = int(limits["rpm"] * self.config.auth_multiplier)
                limits["rph"] = int(limits["rph"] * self.config.auth_multiplier)

            # Verificar si está temporalmente bloqueado
            if await self._is_temporarily_blocked(client_id):
                raise HTTPException(
                    status_code=429,
                    detail="Temporarily blocked due to rate limit violations",
                )

            # Verificar límites de rate limiting
            allowed, limit_info = await self._check_rate_limit(
                client_id, endpoint_key, limits["rpm"], limits["rph"]
            )

            if not allowed:
                # Aplicar bloqueo temporal si es necesario
                if limit_info.get("severe_violation", False):
                    await self._apply_temporary_block(client_id, endpoint_key)

                # Crear respuesta 429
                response = Response(
                    content=json.dumps(
                        {
                            "error": "Rate limit exceeded",
                            "retry_after": limit_info.get("retry_after", 60),
                        }
                    ),
                    status_code=429,
                    media_type="application/json",
                )

                self._add_rate_limit_headers(response, limit_info)
                return response

            # Procesar request normalmente
            response = await call_next(request)

            # Añadir headers de rate limiting
            self._add_rate_limit_headers(response, limit_info)

            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error en RateLimitingMiddleware: {e}")
            # En caso de error, continuar sin rate limiting
            return await call_next(request)

    async def _get_client_identifier(self, request: Request) -> Tuple[str, bool]:
        """
        Obtiene el identificador único del cliente y si está autenticado
        """
        # Intentar obtener usuario autenticado del JWT
        authorization = request.headers.get("Authorization")
        if authorization:
            try:
                scheme, token = get_authorization_scheme_param(authorization)
                if scheme.lower() == "bearer" and token:
                    payload = verify_token(token)
                    if payload and "sub" in payload:
                        # Usar hash del user_id para privacidad
                        user_hash = hashlib.sha256(payload["sub"].encode()).hexdigest()[
                            :16
                        ]
                        return f"user:{user_hash}", True
            except Exception:
                pass  # Continuar con identificación por IP

        # Usar IP como identificador para usuarios no autenticados
        client_ip = self._get_client_ip(request)
        ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:16]
        return f"ip:{ip_hash}", False

    def _get_client_ip(self, request: Request) -> str:
        """
        Obtiene la IP real del cliente considerando proxies
        """
        # Verificar headers de proxy en orden de prioridad
        forwarded_headers = [
            "X-Forwarded-For",
            "X-Real-IP",
            "CF-Connecting-IP",  # Cloudflare
            "X-Client-IP",
        ]

        for header in forwarded_headers:
            if header in request.headers:
                ip = request.headers[header].split(",")[0].strip()
                if ip and ip != "unknown":
                    return ip

        # Fallback a la IP de la conexión
        return request.client.host if request.client else "unknown"

    async def _check_rate_limit(
        self, client_id: str, endpoint: str, rpm_limit: int, rph_limit: int
    ) -> Tuple[bool, Dict]:
        """
        Verifica los límites de rate limiting usando Redis
        """
        if not self.redis_available or not self.redis_client:
            # Modo degradado: permitir todas las requests
            return True, {"remaining_rpm": rpm_limit, "remaining_rph": rph_limit}

        try:
            current_time = int(time.time())
            minute_key = (
                f"rate_limit:{client_id}:{endpoint}:minute:{current_time // 60}"
            )
            hour_key = f"rate_limit:{client_id}:{endpoint}:hour:{current_time // 3600}"

            # Usar pipeline para operaciones atómicas
            pipe = self.redis_client.pipeline()

            # Incrementar contadores
            pipe.incr(minute_key)
            pipe.expire(minute_key, 120)  # Expirar en 2 minutos
            pipe.incr(hour_key)
            pipe.expire(hour_key, 7200)  # Expirar en 2 horas

            results = await pipe.execute()

            minute_count = results[0]
            hour_count = results[2]

            # Verificar límites
            rpm_exceeded = minute_count > rpm_limit
            rph_exceeded = hour_count > rph_limit

            # Calcular información de límites
            limit_info = {
                "remaining_rpm": max(0, rpm_limit - minute_count + 1),
                "remaining_rph": max(0, rph_limit - hour_count + 1),
                "reset_time_rpm": ((current_time // 60) + 1) * 60,
                "reset_time_rph": ((current_time // 3600) + 1) * 3600,
                "usage_ratio": max(minute_count / rpm_limit, hour_count / rph_limit),
                "severe_violation": minute_count > rpm_limit * 2
                or hour_count > rph_limit * 1.5,
            }

            return not (rpm_exceeded or rph_exceeded), limit_info

        except Exception as e:
            logger.error(f"Error verificando rate limit: {e}")
            # En caso de error, permitir la request
            return True, {"remaining_rpm": rpm_limit, "remaining_rph": rph_limit}

    async def _apply_temporary_block(self, client_id: str, endpoint: str):
        """
        Aplica un bloqueo temporal al cliente
        """
        if not self.redis_available or not self.redis_client:
            return

        try:
            block_key = f"rate_limit:blocked:{client_id}"
            block_duration = self.config.block_duration * 60  # Convertir a segundos

            await self.redis_client.setex(
                block_key,
                block_duration,
                json.dumps(
                    {
                        "blocked_at": int(time.time()),
                        "endpoint": endpoint,
                        "duration": block_duration,
                    }
                ),
            )

            logger.warning(
                f"Cliente {client_id} bloqueado temporalmente por {self.config.block_duration} minutos"
            )

        except Exception as e:
            logger.error(f"Error aplicando bloqueo temporal: {e}")

    async def _is_temporarily_blocked(self, client_id: str) -> bool:
        """
        Verifica si un cliente está temporalmente bloqueado
        """
        if not self.redis_available or not self.redis_client:
            return False

        try:
            block_key = f"rate_limit:blocked:{client_id}"
            blocked_info = await self.redis_client.get(block_key)
            return blocked_info is not None

        except Exception as e:
            logger.error(f"Error verificando bloqueo temporal: {e}")
            return False

    def _add_rate_limit_headers(self, response: Response, limit_info: Dict):
        """
        Añade headers de rate limiting a la respuesta con nombres más descriptivos
        """
        # Headers para límites por minuto (más descriptivos)
        response.headers["X-RateLimit-Requests-Per-Minute-Limit"] = str(
            limit_info.get("remaining_rpm", 0) + 1
        )
        response.headers["X-RateLimit-Requests-Per-Minute-Remaining"] = str(
            limit_info.get("remaining_rpm", 0)
        )
        response.headers["X-RateLimit-Requests-Per-Minute-Reset"] = str(
            limit_info.get("reset_time_rpm", 0)
        )

        # Headers para límites por hora (más descriptivos)
        response.headers["X-RateLimit-Requests-Per-Hour-Limit"] = str(
            limit_info.get("remaining_rph", 0) + 1
        )
        response.headers["X-RateLimit-Requests-Per-Hour-Remaining"] = str(
            limit_info.get("remaining_rph", 0)
        )
        response.headers["X-RateLimit-Requests-Per-Hour-Reset"] = str(
            limit_info.get("reset_time_rph", 0)
        )

        if "retry_after" in limit_info:
            response.headers["Retry-After"] = str(limit_info["retry_after"])
