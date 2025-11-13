"""
Configuración centralizada de seguridad y rate limiting
"""

import json
from typing import Dict, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class SecurityConfig(BaseSettings):
    """Configuración de headers de seguridad"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Configuración del entorno
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # Security Headers
    enable_hsts: bool = True
    hsts_max_age: int = 31536000  # 1 año
    hsts_include_subdomains: bool = True
    hsts_preload: bool = True

    # Content Security Policy
    csp_default_src: str = "'self'"
    csp_script_src: str = "'self' 'unsafe-inline' 'unsafe-eval'"
    csp_style_src: str = "'self' 'unsafe-inline'"
    csp_img_src: str = "'self' data: https:"
    csp_font_src: str = "'self' https:"
    csp_connect_src: str = "'self' https:"
    csp_frame_ancestors: str = "'none'"

    # Configuración específica por entorno
    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def csp_policy(self) -> str:
        """Genera la política CSP basada en el entorno"""
        if self.is_production:
            return (
                f"default-src {self.csp_default_src}; "
                f"script-src {self.csp_default_src}; "
                f"style-src {self.csp_default_src}; "
                f"img-src {self.csp_img_src}; "
                f"font-src {self.csp_font_src}; "
                f"connect-src {self.csp_connect_src}; "
                f"frame-ancestors {self.csp_frame_ancestors}; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "upgrade-insecure-requests"
            )
        else:
            return (
                f"default-src {self.csp_default_src}; "
                f"script-src {self.csp_script_src}; "
                f"style-src {self.csp_style_src}; "
                f"img-src {self.csp_img_src}; "
                f"font-src {self.csp_font_src}; "
                f"connect-src {self.csp_connect_src}; "
                f"frame-ancestors {self.csp_frame_ancestors}"
            )

    # Configuración cargada desde .env ya definida arriba


class RateLimitConfig(BaseSettings):
    """Configuración de rate limiting"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Redis
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")

    # Rate Limiting Configuration
    enabled: bool = Field(default=True, alias="RATE_LIMITING_ENABLED")
    default_rpm: int = Field(default=120, alias="RATE_LIMIT_DEFAULT_RPM")
    default_rph: int = Field(default=2400, alias="RATE_LIMIT_DEFAULT_RPH")

    # Valores hardcodeados optimizados para sistema de chat con asesores
    auth_multiplier: float = 3.0  # Multiplicador para usuarios autenticados
    block_duration: int = (
        10  # Duración de bloqueo en segundos (reducido para no afectar servicio)
    )
    alert_threshold: float = 0.85  # Umbral para alertas (más permisivo)

    # Configuración personalizada de endpoints
    endpoint_config_json: Optional[str] = Field(
        default=None, alias="RATE_LIMIT_ENDPOINT_CONFIG"
    )

    @property
    def redis_url(self) -> str:
        """Construye la URL de Redis"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def endpoint_config(self) -> Dict[str, Dict[str, int]]:
        """Parsea la configuración personalizada de endpoints"""
        if not self.endpoint_config_json:
            return {}

        try:
            return json.loads(self.endpoint_config_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    @property
    def default_endpoint_limits(self) -> Dict[str, Dict[str, int]]:
        """Configuración optimizada para sistema de chat con asesores"""
        return {
            # Endpoints críticos (autenticación) - Más restrictivos por seguridad
            "POST /auth/login": {"rpm": 8, "rph": 50},
            "POST /auth/register": {"rpm": 5, "rph": 30},
            "POST /auth/reset-password": {"rpm": 3, "rph": 15},
            "POST /auth/verify-email": {"rpm": 8, "rph": 40},
            # Endpoints de chat - Optimizados para asesores atendiendo múltiples chats
            "POST /api/v1/chats": {"rpm": 80, "rph": 1200},  # Crear nuevos chats
            "PUT /api/v1/chats/*": {"rpm": 100, "rph": 1500},  # Actualizar chats
            "POST /api/v1/chats/*/messages": {
                "rpm": 200,
                "rph": 3000,
            },  # Enviar mensajes (muy frecuente)
            # Endpoints de consulta - Para dashboards y reportes
            "GET /api/v1/chats": {"rpm": 120, "rph": 1800},
            "GET /api/v1/chats/*": {"rpm": 180, "rph": 2200},
            # Endpoints de notificaciones y estado - Para tiempo real
            "GET /api/v1/notifications": {"rpm": 100, "rph": 1500},
            "POST /api/v1/notifications/read": {"rpm": 80, "rph": 1000},
            "GET /api/v1/status": {"rpm": 150, "rph": 2000},
            # Endpoints permisivos (salud, documentación)
            "GET /health": {"rpm": 300, "rph": 3000},
            "GET /health/*": {"rpm": 300, "rph": 3000},
            "GET /docs": {"rpm": 100, "rph": 1000},
            "GET /redoc": {"rpm": 100, "rph": 1000},
            "GET /openapi.json": {"rpm": 50, "rph": 500},
        }

    def get_endpoint_limits(self, method: str, path: str) -> Dict[str, int]:
        """Obtiene los límites para un endpoint específico"""
        endpoint_key = f"{method} {path}"

        # Buscar configuración personalizada primero
        custom_config = self.endpoint_config
        if endpoint_key in custom_config:
            return custom_config[endpoint_key]

        # Buscar en configuración por defecto
        default_config = self.default_endpoint_limits
        if endpoint_key in default_config:
            return default_config[endpoint_key]

        # Buscar patrones con wildcards
        for pattern, limits in default_config.items():
            if "*" in pattern:
                pattern_method, pattern_path = pattern.split(" ", 1)
                if method == pattern_method and self._match_wildcard_path(
                    path, pattern_path
                ):
                    return limits

        # Retornar límites por defecto
        return {"rpm": self.default_rpm, "rph": self.default_rph}

    def _match_wildcard_path(self, path: str, pattern: str) -> bool:
        """Verifica si un path coincide con un patrón con wildcards"""
        if "*" not in pattern:
            return path == pattern

        # Convertir patrón a regex simple
        import re

        regex_pattern = pattern.replace("*", "[^/]+")
        return bool(re.match(f"^{regex_pattern}$", path))


# Instancias globales de configuración
security_config = SecurityConfig()
rate_limit_config = RateLimitConfig()
