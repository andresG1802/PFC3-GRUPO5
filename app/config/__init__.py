"""
Módulo de configuración de la aplicación
"""

from .security import (
    RateLimitConfig,
    SecurityConfig,
    rate_limit_config,
    security_config,
)

__all__ = ["security_config", "rate_limit_config", "SecurityConfig", "RateLimitConfig"]
