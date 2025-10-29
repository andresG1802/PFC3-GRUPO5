"""
Middleware para manejo robusto de errores y timeouts
"""

import time
import traceback
from typing import Callable, Dict, Any
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import httpx

from ..services.waha_client import (
    WAHAConnectionError,
    WAHATimeoutError,
    WAHANotFoundError,
    WAHAAuthenticationError,
)
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware para manejo centralizado de errores"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Procesa la request y maneja errores de forma centralizada

        Args:
            request: Request HTTP
            call_next: Siguiente middleware/handler

        Returns:
            Response HTTP con manejo de errores
        """
        start_time = time.time()
        request_id = self._generate_request_id()

        # Agregar request_id al contexto
        request.state.request_id = request_id

        try:
            # Log de request entrante
            logger.info(
                f"Request iniciada: {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": str(request.query_params),
                    "client_ip": request.client.host if request.client else None,
                },
            )

            # Procesar request
            response = await call_next(request)

            # Calcular duración
            duration_ms = (time.time() - start_time) * 1000

            # Log de respuesta exitosa
            logger.info(
                f"Request completada: {request.method} {request.url.path} - {response.status_code}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )

            # Agregar headers de respuesta
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

            return response

        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000

            # Log del error
            logger.error(
                f"Error en request: {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
                exc_info=True,
            )

            # Convertir excepción a respuesta HTTP
            error_response = self._handle_exception(exc, request_id)
            error_response.headers["X-Request-ID"] = request_id
            error_response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

            return error_response

    def _generate_request_id(self) -> str:
        """Genera un ID único para la request"""
        import uuid

        return str(uuid.uuid4())[:8]

    def _handle_exception(self, exc: Exception, request_id: str) -> JSONResponse:
        """
        Convierte excepciones en respuestas HTTP apropiadas

        Args:
            exc: Excepción capturada
            request_id: ID de la request

        Returns:
            JSONResponse con error formateado
        """
        # Errores de WAHA
        if isinstance(exc, WAHAAuthenticationError):
            return JSONResponse(
                status_code=401,
                content={
                    "error": "authentication_error",
                    "message": "Error de autenticación con WAHA API",
                    "detail": str(exc),
                    "request_id": request_id,
                },
            )

        elif isinstance(exc, WAHANotFoundError):
            return JSONResponse(
                status_code=404,
                content={
                    "error": "not_found",
                    "message": "Recurso no encontrado en WAHA",
                    "detail": str(exc),
                    "request_id": request_id,
                },
            )

        elif isinstance(exc, WAHATimeoutError):
            return JSONResponse(
                status_code=504,
                content={
                    "error": "timeout_error",
                    "message": "Timeout en comunicación con WAHA",
                    "detail": str(exc),
                    "request_id": request_id,
                },
            )

        elif isinstance(exc, WAHAConnectionError):
            return JSONResponse(
                status_code=503,
                content={
                    "error": "service_unavailable",
                    "message": "Servicio WAHA no disponible",
                    "detail": str(exc),
                    "request_id": request_id,
                },
            )

        # Errores HTTP de FastAPI
        elif isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": "http_error",
                    "message": exc.detail,
                    "request_id": request_id,
                },
            )

        # Errores de validación de Pydantic
        elif hasattr(exc, "errors") and callable(getattr(exc, "errors")):
            return JSONResponse(
                status_code=422,
                content={
                    "error": "validation_error",
                    "message": "Error de validación de datos",
                    "detail": exc.errors(),
                    "request_id": request_id,
                },
            )

        # Errores de conexión HTTP
        elif isinstance(exc, httpx.ConnectError):
            return JSONResponse(
                status_code=503,
                content={
                    "error": "connection_error",
                    "message": "Error de conexión con servicio externo",
                    "detail": "No se pudo establecer conexión",
                    "request_id": request_id,
                },
            )

        elif isinstance(exc, httpx.TimeoutException):
            return JSONResponse(
                status_code=504,
                content={
                    "error": "timeout_error",
                    "message": "Timeout en operación",
                    "detail": "La operación tardó demasiado tiempo",
                    "request_id": request_id,
                },
            )

        # Error genérico del servidor
        else:
            logger.critical(
                f"Error no manejado: {type(exc).__name__}",
                extra={
                    "request_id": request_id,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )

            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "message": "Error interno del servidor",
                    "detail": "Ha ocurrido un error inesperado",
                    "request_id": request_id,
                },
            )


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Middleware para manejo de timeouts globales"""

    def __init__(self, app: ASGIApp, timeout_seconds: float = 30.0):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Aplica timeout global a todas las requests

        Args:
            request: Request HTTP
            call_next: Siguiente middleware/handler

        Returns:
            Response HTTP o error de timeout
        """
        import asyncio

        try:
            # Aplicar timeout a la request
            response = await asyncio.wait_for(
                call_next(request), timeout=self.timeout_seconds
            )
            return response

        except asyncio.TimeoutError:
            request_id = getattr(request.state, "request_id", "unknown")

            logger.warning(
                f"Request timeout: {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "timeout_seconds": self.timeout_seconds,
                },
            )

            return JSONResponse(
                status_code=504,
                content={
                    "error": "request_timeout",
                    "message": f"Request excedió el timeout de {self.timeout_seconds} segundos",
                    "request_id": request_id,
                },
            )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware básico para rate limiting"""

    def __init__(self, app: ASGIApp, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts: Dict[str, Dict[str, Any]] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Aplica rate limiting por IP

        Args:
            request: Request HTTP
            call_next: Siguiente middleware/handler

        Returns:
            Response HTTP o error de rate limit
        """
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        # Limpiar contadores antiguos
        self._cleanup_old_requests(current_time)

        # Verificar rate limit
        if self._is_rate_limited(client_ip, current_time):
            logger.warning(
                f"Rate limit excedido para IP: {client_ip}",
                extra={
                    "client_ip": client_ip,
                    "requests_per_minute": self.requests_per_minute,
                },
            )

            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"Demasiadas requests. Límite: {self.requests_per_minute} por minuto",
                    "retry_after": 60,
                },
                headers={"Retry-After": "60"},
            )

        # Registrar request
        self._record_request(client_ip, current_time)

        return await call_next(request)

    def _cleanup_old_requests(self, current_time: float) -> None:
        """Limpia contadores de requests antiguas"""
        cutoff_time = current_time - 60  # 1 minuto atrás

        for ip in list(self.request_counts.keys()):
            self.request_counts[ip]["requests"] = [
                req_time
                for req_time in self.request_counts[ip]["requests"]
                if req_time > cutoff_time
            ]

            # Eliminar IPs sin requests recientes
            if not self.request_counts[ip]["requests"]:
                del self.request_counts[ip]

    def _is_rate_limited(self, client_ip: str, current_time: float) -> bool:
        """Verifica si la IP está rate limited"""
        if client_ip not in self.request_counts:
            return False

        recent_requests = len(self.request_counts[client_ip]["requests"])
        return recent_requests >= self.requests_per_minute

    def _record_request(self, client_ip: str, current_time: float) -> None:
        """Registra una nueva request"""
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = {"requests": []}

        self.request_counts[client_ip]["requests"].append(current_time)
