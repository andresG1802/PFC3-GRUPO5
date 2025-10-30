"""Cliente HTTP para comunicación con WAHA (WhatsApp HTTP API)"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from functools import wraps
import time

import httpx

from ..api.envs import WAHA_API_KEY, WAHA_ENCRYPTION_KEY
from ..utils.logging_config import LoggerMixin


# Configurar logging
logger = logging.getLogger(__name__)


class WAHAConnectionError(Exception):
    """Error de conexión con WAHA"""

    pass


class WAHAAuthenticationError(Exception):
    """Error de autenticación con WAHA"""

    pass


class WAHANotFoundError(Exception):
    """Recurso no encontrado en WAHA"""

    pass


class WAHATimeoutError(Exception):
    """Timeout en la comunicación con WAHA"""

    pass


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """Decorador para reintentar operaciones fallidas"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (
                    httpx.ConnectError,
                    httpx.TimeoutException,
                    WAHAConnectionError,
                ) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (2**attempt)  # Backoff exponencial
                        logger.warning(
                            f"Intento {attempt + 1} falló, reintentando en {wait_time}s: {e}"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"Todos los intentos fallaron: {e}")
                except Exception as e:
                    # No reintentar para otros tipos de errores
                    raise e
            raise last_exception

        return wrapper

    return decorator


class WAHAClient(LoggerMixin):
    """Cliente para comunicación con WAHA API"""

    def __init__(
        self, base_url: str = "http://waha:8000", session_name: str = "default"
    ):
        """
        Inicializa el cliente WAHA

        Args:
            base_url: URL base de WAHA (por defecto usa el servicio Docker)
            session_name: Nombre de la sesión de WhatsApp
        """
        self.base_url = base_url.rstrip("/")
        self.session_name = session_name
        self.api_key = WAHA_API_KEY

        # Configurar cliente HTTP con timeouts
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"},
        )

        self.log_operation(
            "client_initialized", base_url=base_url, session=session_name
        )

    async def __aenter__(self):
        """Entrada del context manager"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Salida del context manager"""
        await self.close()

    async def close(self):
        """Cierra el cliente HTTP"""
        await self.client.aclose()
        logger.info("Cliente WAHA cerrado")

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """
        Maneja la respuesta HTTP y convierte errores

        Args:
            response: Respuesta HTTP de WAHA

        Returns:
            Dict con los datos de respuesta

        Raises:
            WAHAAuthenticationError: Error de autenticación
            WAHANotFoundError: Recurso no encontrado
            WAHAConnectionError: Error de conexión o servidor
        """
        try:
            if response.status_code == 401:
                self.log_error(
                    "authentication_failed",
                    WAHAAuthenticationError("API Key inválida o sesión no autorizada"),
                    status_code=response.status_code,
                )
                raise WAHAAuthenticationError("API Key inválida o sesión no autorizada")
            elif response.status_code == 404:
                self.log_error(
                    "resource_not_found",
                    WAHANotFoundError("Recurso no encontrado"),
                    status_code=response.status_code,
                    url=str(response.url),
                )
                raise WAHANotFoundError("Recurso no encontrado")
            elif response.status_code >= 500:
                error = WAHAConnectionError(
                    f"Error del servidor WAHA: {response.status_code}"
                )
                self.log_error("server_error", error, status_code=response.status_code)
                raise error
            elif response.status_code >= 400:
                error_detail = response.text
                error = WAHAConnectionError(
                    f"Error en la solicitud: {response.status_code} - {error_detail}"
                )
                self.log_error(
                    "client_error",
                    error,
                    status_code=response.status_code,
                    detail=error_detail,
                )
                raise error

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            raise WAHAConnectionError(f"Error HTTP: {e.response.status_code}")
        except Exception as e:
            if isinstance(
                e, (WAHAAuthenticationError, WAHANotFoundError, WAHAConnectionError)
            ):
                raise
            raise WAHAConnectionError(f"Error procesando respuesta: {str(e)}")

    @retry_on_failure(max_retries=3, delay=1.0)
    async def get_session_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado de la sesión de WhatsApp

        Returns:
            Dict con información del estado de la sesión
        """
        try:
            url = f"{self.base_url}/api/sessions/{self.session_name}"
            logger.debug(f"Obteniendo estado de sesión: {url}")

            response = await self.client.get(url)
            data = self._handle_response(response)

            logger.info(f"Estado de sesión obtenido: {data.get('status', 'unknown')}")
            return data

        except httpx.TimeoutException:
            raise WAHATimeoutError("Timeout al obtener estado de sesión")
        except httpx.ConnectError:
            raise WAHAConnectionError("No se pudo conectar con WAHA")

    @retry_on_failure(max_retries=3, delay=1.0)
    async def get_chats(self, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Obtiene lista de chats desde WAHA

        Args:
            limit: Número máximo de chats a obtener
            offset: Desplazamiento para paginación

        Returns:
            Lista de chats en formato WAHA
        """
        start_time = time.time()

        try:
            url = f"{self.base_url}/api/{self.session_name}/chats"
            params = {"limit": limit, "offset": offset}

            self.log_operation("get_chats_request", url=url, limit=limit, offset=offset)

            response = await self.client.get(url, params=params)
            data = self._handle_response(response)

            # WAHA puede devolver directamente una lista o un objeto con lista
            chats = data if isinstance(data, list) else data.get("chats", [])

            duration_ms = (time.time() - start_time) * 1000
            self.log_performance(
                "get_chats",
                duration_ms,
                chat_count=len(chats),
                limit=limit,
                offset=offset,
            )

            return chats

        except httpx.TimeoutException as e:
            duration_ms = (time.time() - start_time) * 1000
            self.log_error(
                "get_chats_timeout",
                e,
                duration_ms=duration_ms,
                limit=limit,
                offset=offset,
            )
            raise WAHATimeoutError("Timeout al obtener chats")
        except httpx.ConnectError as e:
            duration_ms = (time.time() - start_time) * 1000
            self.log_error(
                "get_chats_connection",
                e,
                duration_ms=duration_ms,
                limit=limit,
                offset=offset,
            )
            raise WAHAConnectionError("No se pudo conectar con WAHA")

    @retry_on_failure(max_retries=3, delay=1.0)
    async def get_chats_overview(
        self, limit: int = 20, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Obtiene vista general de chats optimizada desde WAHA

        Args:
            limit: Número máximo de chats a obtener
            offset: Desplazamiento para paginación

        Returns:
            Lista de chats en formato overview
        """
        try:
            url = f"{self.base_url}/api/{self.session_name}/chats/overview"
            params = {"limit": limit, "offset": offset}

            logger.debug(f"Obteniendo overview de chats: {url} - Params: {params}")

            response = await self.client.get(url, params=params)
            data = self._handle_response(response)

            # WAHA puede devolver directamente una lista o un objeto con lista
            chats = data if isinstance(data, list) else data.get("chats", [])

            logger.info(f"Obtenidos {len(chats)} chats overview desde WAHA")
            return chats

        except httpx.TimeoutException:
            raise WAHATimeoutError("Timeout al obtener chats overview")
        except httpx.ConnectError:
            raise WAHAConnectionError("No se pudo conectar con WAHA")

    @retry_on_failure(max_retries=3, delay=1.0)
    async def get_chat_by_id(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un chat específico por ID

        Args:
            chat_id: ID del chat a obtener

        Returns:
            Datos del chat o None si no existe
        """
        try:
            # Primero intentamos obtener el chat desde la lista general
            chats = await self.get_chats(limit=100)  # Límite alto para buscar

            for chat in chats:
                if chat.get("id") == chat_id:
                    logger.info(f"Chat encontrado: {chat_id}")
                    return chat

            logger.warning(f"Chat no encontrado: {chat_id}")
            return None

        except WAHANotFoundError:
            logger.warning(f"Chat no encontrado: {chat_id}")
            return None
        except httpx.TimeoutException:
            raise WAHATimeoutError(f"Timeout al obtener chat {chat_id}")
        except httpx.ConnectError:
            raise WAHAConnectionError("No se pudo conectar con WAHA")

    def _normalize_chat_data(self, waha_chat: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza los datos de chat desde formato WAHA a nuestro formato

        Args:
            waha_chat: Datos del chat en formato WAHA

        Returns:
            Datos del chat normalizados
        """
        try:
            # Mapear tipo de chat
            chat_type = ChatType.INDIVIDUAL
            if waha_chat.get("isGroup", False):
                chat_type = ChatType.GROUP
            elif waha_chat.get("isBroadcast", False):
                chat_type = ChatType.BROADCAST

            # Normalizar último mensaje si existe
            last_message = None
            if "lastMessage" in waha_chat and waha_chat["lastMessage"]:
                msg = waha_chat["lastMessage"]
                last_message = {
                    "id": msg.get("id", ""),
                    "timestamp": msg.get("timestamp", 0),
                    "from_me": msg.get("fromMe", False),
                    "type": msg.get("type", MessageType.TEXT),
                    "body": msg.get("body", ""),
                    "ack": msg.get("ack", MessageAck.PENDING),
                }

            # Normalizar información de contacto
            contact = None
            if "contact" in waha_chat and waha_chat["contact"]:
                contact_data = waha_chat["contact"]
                contact = {
                    "id": contact_data.get("id", waha_chat.get("id", "")),
                    "name": contact_data.get("name"),
                    "pushname": contact_data.get("pushname"),
                    "short_name": contact_data.get("shortName"),
                    "is_business": contact_data.get("isBusiness", False),
                    "is_enterprise": contact_data.get("isEnterprise", False),
                }

            normalized = {
                "id": waha_chat.get("id", ""),
                "name": waha_chat.get("name") or waha_chat.get("formattedTitle", ""),
                "type": chat_type,
                "timestamp": waha_chat.get("timestamp"),
                "unread_count": waha_chat.get("unreadCount", 0),
                "archived": waha_chat.get("archived", False),
                "pinned": waha_chat.get("pinned", False),
                "muted": waha_chat.get("muted", False),
                "contact": contact,
                "last_message": last_message,
                "picture_url": waha_chat.get("pictureUrl"),
            }

            return normalized

        except Exception as e:
            logger.error(f"Error normalizando datos de chat: {e}")
            # Retornar estructura mínima en caso de error
            return {
                "id": waha_chat.get("id", ""),
                "name": waha_chat.get("name", "Chat sin nombre"),
                "type": ChatType.INDIVIDUAL,
                "timestamp": None,
                "unread_count": 0,
                "archived": False,
                "pinned": False,
                "muted": False,
                "contact": None,
                "last_message": None,
                "picture_url": None,
            }

    @retry_on_failure(max_retries=3, delay=1.0)
    async def get_messages(
        self, chat_id: str, limit: int = 20, offset: int = 0
    ) -> Dict[str, Any]:
        """
        Obtiene mensajes de un chat específico

        Args:
            chat_id: ID del chat
            limit: Número máximo de mensajes a obtener
            offset: Número de mensajes a omitir

        Returns:
            Dict con mensajes y total
        """
        start_time = time.time()
        try:
            url = f"{self.base_url}/api/{self.session_name}/chats/{chat_id}/messages"
            params = {"limit": limit, "offset": offset}

            logger.debug(f"Obteniendo mensajes: {url} con params: {params}")

            response = await self.client.get(url, params=params)
            data = self._handle_response(response)

            duration_ms = (time.time() - start_time) * 1000
            self.log_operation(
                "get_messages_success",
                duration_ms=duration_ms,
                chat_id=chat_id,
                limit=limit,
                offset=offset,
                total=data.get("total", 0),
            )

            return data

        except httpx.TimeoutException as e:
            duration_ms = (time.time() - start_time) * 1000
            self.log_error(
                "get_messages_timeout",
                e,
                duration_ms=duration_ms,
                chat_id=chat_id,
                limit=limit,
                offset=offset,
            )
            raise WAHATimeoutError("Timeout al obtener mensajes")
        except httpx.ConnectError as e:
            duration_ms = (time.time() - start_time) * 1000
            self.log_error(
                "get_messages_connection",
                e,
                duration_ms=duration_ms,
                chat_id=chat_id,
                limit=limit,
                offset=offset,
            )
            raise WAHAConnectionError("No se pudo conectar con WAHA")

    @retry_on_failure(max_retries=3, delay=1.0)
    async def send_message(
        self, chat_id: str, message: str, message_type: str = "text"
    ) -> Dict[str, Any]:
        """
        Envía un mensaje a un chat específico

        Args:
            chat_id: ID del chat
            message: Contenido del mensaje
            message_type: Tipo de mensaje (text, image, etc.)

        Returns:
            Dict con información del mensaje enviado
        """
        start_time = time.time()
        try:
            url = f"{self.base_url}/api/{self.session_name}/chats/{chat_id}/messages"
            payload = {"text": message, "type": message_type}

            logger.debug(f"Enviando mensaje: {url} con payload: {payload}")

            response = await self.client.post(url, json=payload)
            data = self._handle_response(response)

            duration_ms = (time.time() - start_time) * 1000
            self.log_operation(
                "send_message_success",
                duration_ms=duration_ms,
                chat_id=chat_id,
                message_type=message_type,
                message_id=data.get("id"),
            )

            return data

        except httpx.TimeoutException as e:
            duration_ms = (time.time() - start_time) * 1000
            self.log_error(
                "send_message_timeout",
                e,
                duration_ms=duration_ms,
                chat_id=chat_id,
                message_type=message_type,
            )
            raise WAHATimeoutError("Timeout al enviar mensaje")
        except httpx.ConnectError as e:
            duration_ms = (time.time() - start_time) * 1000
            self.log_error(
                "send_message_connection",
                e,
                duration_ms=duration_ms,
                chat_id=chat_id,
                message_type=message_type,
            )
            raise WAHAConnectionError("No se pudo conectar con WAHA")


# Instancia global del cliente (se inicializa cuando se necesite)
_waha_client: Optional[WAHAClient] = None


async def get_waha_client() -> WAHAClient:
    """
    Obtiene la instancia global del cliente WAHA

    Returns:
        Instancia del cliente WAHA
    """
    global _waha_client

    if _waha_client is None:
        # Detectar si estamos en Docker o local
        try:
            # Intentar conectar con el servicio Docker primero
            _waha_client = WAHAClient("http://waha:8000")
            await _waha_client.get_session_status()
            logger.info("Conectado a WAHA via Docker")
        except:
            try:
                # Fallback a localhost (para desarrollo local)
                _waha_client = WAHAClient("http://localhost:3000")
                await _waha_client.get_session_status()
                logger.info("Conectado a WAHA via localhost")
            except Exception as e:
                logger.error(f"No se pudo conectar a WAHA: {e}")
                raise WAHAConnectionError("No se pudo establecer conexión con WAHA")

    return _waha_client


async def close_waha_client():
    """Cierra la instancia global del cliente WAHA"""
    global _waha_client
    if _waha_client:
        await _waha_client.close()
        _waha_client = None
        logger.info("Cliente WAHA global cerrado")
