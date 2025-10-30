"""
Configuración de logging para la aplicación
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import json

from ..api.envs import DEBUG


class JSONFormatter(logging.Formatter):
    """Formateador JSON para logs estructurados"""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Agregar información adicional si está disponible
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id

        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id

        if hasattr(record, "chat_id"):
            log_entry["chat_id"] = record.chat_id

        if hasattr(record, "operation"):
            log_entry["operation"] = record.operation

        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        # Agregar información de excepción si existe
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """Formateador con colores para consola"""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]

        # Formato: [TIMESTAMP] LEVEL - MODULE.FUNCTION:LINE - MESSAGE
        formatted = (
            f"{color}[{datetime.fromtimestamp(record.created).strftime('%H:%M:%S')}] "
            f"{record.levelname:<8}{reset} - "
            f"{record.module}.{record.funcName}:{record.lineno} - "
            f"{record.getMessage()}"
        )

        # Agregar información adicional si está disponible
        extras = []
        if hasattr(record, "request_id"):
            extras.append(f"req_id={record.request_id}")
        if hasattr(record, "chat_id"):
            extras.append(f"chat_id={record.chat_id}")
        if hasattr(record, "duration_ms"):
            extras.append(f"duration={record.duration_ms}ms")

        if extras:
            formatted += f" [{', '.join(extras)}]"

        return formatted


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    enable_json_logs: bool = False,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """
    Configura el sistema de logging

    Args:
        log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Archivo de log (opcional)
        enable_json_logs: Habilitar logs en formato JSON
        max_file_size: Tamaño máximo del archivo de log en bytes
        backup_count: Número de archivos de backup a mantener
    """
    # Convertir nivel de string a constante
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configurar logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Limpiar handlers existentes
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)

    if enable_json_logs:
        console_formatter = JSONFormatter()
    else:
        console_formatter = ColoredFormatter()

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Handler para archivo si se especifica
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_file_size, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setLevel(numeric_level)

        # Siempre usar JSON para archivos
        file_formatter = JSONFormatter()
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Configurar loggers específicos
    configure_specific_loggers(numeric_level)

    logging.info(f"Logging configurado - Nivel: {log_level}, Archivo: {log_file}")


def configure_specific_loggers(level: int) -> None:
    """Configura loggers específicos para diferentes módulos"""

    # Logger para WAHA client
    waha_logger = logging.getLogger("app.services.waha_client")
    waha_logger.setLevel(level)

    # Logger para cache
    cache_logger = logging.getLogger("app.services.cache")
    cache_logger.setLevel(level)

    # Logger para endpoints de chats
    chats_logger = logging.getLogger("app.api.v1.chats")
    chats_logger.setLevel(level)

    # Logger para base de datos
    db_logger = logging.getLogger("app.database")
    db_logger.setLevel(level)

    # Reducir verbosidad de librerías externas
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    # Silenciar logs de MongoDB/PyMongo
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("pymongo.command").setLevel(logging.WARNING)
    logging.getLogger("pymongo.connection").setLevel(logging.WARNING)
    logging.getLogger("pymongo.server").setLevel(logging.WARNING)
    logging.getLogger("pymongo.topology").setLevel(logging.WARNING)
    logging.getLogger("pymongo.serverSelection").setLevel(logging.WARNING)
    
    # Silenciar otros loggers verbosos
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("aiofiles").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)

    # En desarrollo, mostrar más detalles de FastAPI
    if DEBUG:
        logging.getLogger("uvicorn").setLevel(logging.INFO)
        logging.getLogger("fastapi").setLevel(logging.INFO)
    else:
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
        logging.getLogger("fastapi").setLevel(logging.WARNING)


class LoggerMixin:
    """Mixin para agregar logging contextual a clases"""

    @property
    def logger(self) -> logging.Logger:
        """Obtiene logger específico para la clase"""
        return logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    def log_operation(self, operation: str, **kwargs) -> None:
        """Log de operación con contexto adicional"""
        extra = {"operation": operation}
        extra.update(kwargs)
        self.logger.info(f"Ejecutando operación: {operation}", extra=extra)

    def log_error(self, operation: str, error: Exception, **kwargs) -> None:
        """Log de error con contexto adicional"""
        extra = {"operation": operation}
        extra.update(kwargs)
        self.logger.error(
            f"Error en operación {operation}: {str(error)}", extra=extra, exc_info=True
        )

    def log_performance(self, operation: str, duration_ms: float, **kwargs) -> None:
        """Log de rendimiento con métricas"""
        extra = {"operation": operation, "duration_ms": duration_ms}
        extra.update(kwargs)

        if duration_ms > 1000:  # Más de 1 segundo
            self.logger.warning(
                f"Operación lenta: {operation} ({duration_ms:.2f}ms)", extra=extra
            )
        else:
            self.logger.debug(
                f"Operación completada: {operation} ({duration_ms:.2f}ms)", extra=extra
            )


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene un logger con nombre específico

    Args:
        name: Nombre del logger

    Returns:
        Logger configurado
    """
    return logging.getLogger(name)


def log_request_context(request_id: str, user_id: Optional[str] = None):
    """
    Decorador para agregar contexto de request a los logs

    Args:
        request_id: ID único de la request
        user_id: ID del usuario (opcional)
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Agregar contexto al logger
            logger = logging.getLogger(func.__module__)

            # Crear un adaptador con contexto
            class ContextAdapter(logging.LoggerAdapter):
                def process(self, msg, kwargs):
                    extra = kwargs.get("extra", {})
                    extra.update({"request_id": request_id, "user_id": user_id})
                    kwargs["extra"] = extra
                    return msg, kwargs

            # Reemplazar temporalmente el logger
            original_logger = func.__globals__.get("logger")
            if original_logger:
                func.__globals__["logger"] = ContextAdapter(original_logger, {})

            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                # Restaurar logger original
                if original_logger:
                    func.__globals__["logger"] = original_logger

        return wrapper

    return decorator


# Configuración por defecto
def init_logging():
    """Inicializa el logging con configuración por defecto"""
    # Usar WARNING como nivel por defecto para reducir verbosidad
    log_level = "INFO" if DEBUG else "WARNING"
    log_file = "logs/app.log" if not DEBUG else None

    setup_logging(
        log_level=log_level,
        log_file=log_file,
        enable_json_logs=not DEBUG,  # JSON en producción, colores en desarrollo
        max_file_size=10 * 1024 * 1024,  # 10MB
        backup_count=5,
    )
