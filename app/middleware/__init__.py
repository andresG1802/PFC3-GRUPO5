"""
Módulo de middleware para la aplicación FastAPI
"""

from .security import SecurityHeadersMiddleware

__all__ = ["SecurityHeadersMiddleware"]
