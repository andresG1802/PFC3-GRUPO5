"""Middleware de seguridad para agregar headers de seguridad a todas las respuestas HTTP"""

import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware que agrega headers de seguridad a todas las respuestas HTTP
    con configuración centralizada y soporte para diferentes entornos
    """

    def __init__(self, app):
        super().__init__(app)
        # Definir los headers de seguridad que se agregarán a todas las respuestas
        self.security_headers = {
            "Content-Security-Policy": (
                "default-src 'self';"
                "base-uri 'self';"
                "font-src 'self' https: data:;"
                "form-action 'self';"
                "frame-ancestors 'self';"
                "img-src 'self' data: https:;"
                "object-src 'none';"
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;"
                "script-src-attr 'none';"
                "style-src 'self' https: 'unsafe-inline';"
                "upgrade-insecure-requests"
            ),
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-origin",
            "Origin-Agent-Cluster": "?1",
            "Referrer-Policy": "no-referrer",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "X-Content-Type-Options": "nosniff",
            "X-DNS-Prefetch-Control": "off",
            "X-Download-Options": "noopen",
            "X-Frame-Options": "SAMEORIGIN",
            "X-Permitted-Cross-Domain-Policies": "none",
            "X-XSS-Protection": "0",
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Procesa la request y agrega headers de seguridad a la response

        Args:
            request: La request HTTP entrante
            call_next: La siguiente función en la cadena de middleware

        Returns:
            Response: La response con headers de seguridad agregados
        """
        try:
            # Procesar la request normalmente
            response = await call_next(request)

            # Agregar headers de seguridad a la response
            self._add_security_headers(response)

            # Remover headers que pueden revelar información del servidor
            self._remove_server_headers(response)

            return response

        except Exception as e:
            logger.error(f"Error in SecurityHeadersMiddleware: {str(e)}")

            # En caso de error, continuar sin los headers de seguridad
            return await call_next(request)

    def _add_security_headers(self, response: Response) -> None:
        """Añade todos los headers de seguridad necesarios"""

        # Agregar todos los headers de seguridad definidos
        for header_name, header_value in self.security_headers.items():
            response.headers[header_name] = header_value

    def _remove_server_headers(self, response: Response) -> None:
        """Remueve headers que revelan información del servidor"""
        headers_to_remove = [
            "Server",
            "server",
            "X-Powered-By",
        ]

        for header in headers_to_remove:
            if header in response.headers:
                del response.headers[header]
