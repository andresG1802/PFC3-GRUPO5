"""
Middleware de seguridad para agregar headers de seguridad a todas las respuestas HTTP
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware que agrega headers de seguridad a todas las respuestas HTTP
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
        # Procesar la request normalmente
        response = await call_next(request)

        # Agregar headers de seguridad a la response
        for header_name, header_value in self.security_headers.items():
            response.headers[header_name] = header_value

        # Remover el header X-Powered-By si está presente
        if "X-Powered-By" in response.headers:
            del response.headers["X-Powered-By"]

        return response
