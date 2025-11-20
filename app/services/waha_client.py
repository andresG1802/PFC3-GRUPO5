"""Cliente HTTP para comunicación con WAHA (WhatsApp HTTP API)"""

import asyncio
import logging
import time
from functools import wraps
from typing import Any, Dict, List, Optional

import httpx

from ..api.envs import WAHA_API_KEY
from ..api.models.chats import ChatType, MessageAck, MessageType
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
            timeout=httpx.Timeout(8.0, connect=4.0),
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
            url = f"{self.base_url}/api/{self.session_name}/chats/overview"
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
        self, limit: int = 20, offset: int = 0, ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get an optimized chats overview from WAHA using GET.

        WAHA responde con overview en `GET /api/{session}/chats/overview`.
        Si se proporcionan `ids`, intentaremos pasarlos como query param
        (si no son soportados, aplicaremos filtrado local en el caller).

        Args:
            limit: Max chats to fetch
            offset: Pagination offset
            ids: Optional list of chat ids to filter

        Returns:
            List of overview chat objects
        """
        try:
            url = f"{self.base_url}/api/{self.session_name}/chats/overview"
            params: Dict[str, Any] = {"limit": limit, "offset": offset}
            if ids:
                # En caso de soporte, pasar ids como query; algunos servidores aceptan ids repetidos
                params["ids"] = ids

            logger.debug(
                f"Obteniendo overview de chats (GET): {url} - Params: {params}"
            )

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

                # Mapear ACK numérico de WAHA al enum MessageAck
                def _map_message_ack(ack_value: Any) -> Optional[MessageAck]:
                    try:
                        if ack_value is None:
                            return None
                        if isinstance(ack_value, int):
                            mapping = {
                                -1: MessageAck.ERROR,
                                0: MessageAck.PENDING,
                                1: MessageAck.SERVER,
                                2: MessageAck.DEVICE,
                                3: MessageAck.READ,
                                4: MessageAck.PLAYED,
                            }
                            return mapping.get(ack_value, MessageAck.PENDING)
                        if isinstance(ack_value, str):
                            # Aceptar valores string en cualquier casing
                            try:
                                return MessageAck(ack_value.upper())
                            except Exception:
                                return MessageAck.PENDING
                        return MessageAck.PENDING
                    except Exception:
                        return MessageAck.PENDING

                last_message = {
                    "id": msg.get("id", ""),
                    "timestamp": msg.get("timestamp", 0),
                    "from_me": msg.get("fromMe", False),
                    "type": msg.get("type", MessageType.TEXT),
                    "body": msg.get("body", ""),
                    "ack": _map_message_ack(msg.get("ack")),
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
        self, chat_id: str, message: str, message_type: str = "text", **kwargs
    ) -> Dict[str, Any]:
        """
        Send a message using WAHA official endpoints.

        Routing:
        - text      -> POST /api/sendText
        - image     -> POST /api/sendFile
        - document  -> POST /api/sendFile
        - audio     -> POST /api/sendFile
        - voice     -> POST /api/sendVoice
        - video     -> POST /api/sendVideo

        Unsupported in this client for now: location, contact, sticker.
        """
        start_time = time.time()
        try:
            mt = (message_type or "text").lower()

            if mt == "text":
                data = await self._send_text_fallback(
                    chat_id, message, **kwargs
                )  # primary path
            elif mt in ("image", "document", "audio"):
                data = await self._send_file(
                    chat_id,
                    kwargs.get("media_url"),
                    filename=kwargs.get("filename"),
                    caption=kwargs.get("caption"),
                )
            elif mt == "voice":
                data = await self._send_voice(chat_id, kwargs.get("media_url"))
            elif mt == "video":
                data = await self._send_video(
                    chat_id, kwargs.get("media_url"), caption=kwargs.get("caption")
                )
            else:
                raise WAHAConnectionError(
                    f"Tipo de mensaje no soportado por WAHAClient: {message_type}"
                )

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

    async def _send_text_fallback(
        self, chat_id: str, text: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Primary method for sending text messages via /api/sendText.
        """
        start_time = time.time()
        url = f"{self.base_url}/api/sendText"

        payload: Dict[str, Any] = {
            "chatId": chat_id,
            "text": text,
            "session": self.session_name,
        }

        # Mapear solo campos relevantes para sendText
        try:
            if isinstance(kwargs, dict) and kwargs:
                if kwargs.get("reply_to"):
                    payload["reply_to"] = kwargs.get("reply_to")
                # Si se proporcionan flags de vista previa de links, pasar también
                if "linkPreview" in kwargs:
                    payload["linkPreview"] = kwargs.get("linkPreview")
                if "linkPreviewHighQuality" in kwargs:
                    payload["linkPreviewHighQuality"] = kwargs.get(
                        "linkPreviewHighQuality"
                    )
        except Exception:
            pass

        logger.debug(f"Fallback sendText: {url} con payload: {payload}")

        response = await self.client.post(url, json=payload)
        data = self._handle_response(response)

        duration_ms = (time.time() - start_time) * 1000
        self.log_operation(
            "send_text_fallback_success",
            duration_ms=duration_ms,
            chat_id=chat_id,
            message_type="text",
            message_id=data.get("id"),
        )

        return data

    async def _send_file(
        self,
        chat_id: str,
        url_or_media: Optional[str],
        *,
        filename: Optional[str] = None,
        caption: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a file (image/document/audio) via /api/sendFile using URL.
        """
        if not url_or_media:
            raise WAHAConnectionError("media_url requerido para enviar archivo")
        start_time = time.time()
        url = f"{self.base_url}/api/sendFile"
        payload: Dict[str, Any] = {
            "chatId": chat_id,
            "url": url_or_media,
            "session": self.session_name,
        }
        if filename:
            payload["filename"] = filename
        if caption:
            payload["caption"] = caption

        logger.debug(f"sendFile: {url} con payload: {payload}")
        response = await self.client.post(url, json=payload)
        data = self._handle_response(response)
        duration_ms = (time.time() - start_time) * 1000
        self.log_operation(
            "send_file_success",
            duration_ms=duration_ms,
            chat_id=chat_id,
            message_type="file",
            message_id=data.get("id"),
        )
        return data

    async def _send_voice(
        self, chat_id: str, url_or_media: Optional[str]
    ) -> Dict[str, Any]:
        """
        Send a voice note via /api/sendVoice using URL.
        """
        if not url_or_media:
            raise WAHAConnectionError("media_url requerido para enviar voz")
        start_time = time.time()
        url = f"{self.base_url}/api/sendVoice"
        payload: Dict[str, Any] = {
            "chatId": chat_id,
            "url": url_or_media,
            "session": self.session_name,
        }
        logger.debug(f"sendVoice: {url} con payload: {payload}")
        response = await self.client.post(url, json=payload)
        data = self._handle_response(response)
        duration_ms = (time.time() - start_time) * 1000
        self.log_operation(
            "send_voice_success",
            duration_ms=duration_ms,
            chat_id=chat_id,
            message_type="voice",
            message_id=data.get("id"),
        )
        return data

    async def _send_video(
        self,
        chat_id: str,
        url_or_media: Optional[str],
        *,
        caption: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a video via /api/sendVideo using URL.
        """
        if not url_or_media:
            raise WAHAConnectionError("media_url requerido para enviar video")
        start_time = time.time()
        url = f"{self.base_url}/api/sendVideo"
        payload: Dict[str, Any] = {
            "chatId": chat_id,
            "url": url_or_media,
            "session": self.session_name,
        }
        if caption:
            payload["caption"] = caption
        logger.debug(f"sendVideo: {url} con payload: {payload}")
        response = await self.client.post(url, json=payload)
        data = self._handle_response(response)
        duration_ms = (time.time() - start_time) * 1000
        self.log_operation(
            "send_video_success",
            duration_ms=duration_ms,
            chat_id=chat_id,
            message_type="video",
            message_id=data.get("id"),
        )
        return data

    @retry_on_failure(max_retries=3, delay=1.0)
    async def configure_webhooks(
        self,
        webhooks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Configura uno o varios webhooks de sesión en WAHA.

        Args:
            webhooks: Lista de objetos con al menos la clave `url` y opcionalmente `events`.

        Returns:
            Dict con el payload de respuesta de WAHA.

        Raises:
            WAHATimeoutError: Cuando WAHA no responde dentro del timeout.
            WAHAConnectionError: Cuando ocurre un error de conexión o servidor.
            WAHAAuthenticationError: Cuando la API Key es inválida.
        """
        if not webhooks:
            raise ValueError("Debe proporcionar al menos un webhook para configurar")

        try:
            session_payload: Dict[str, Any] = {
                "name": self.session_name,
                "config": {
                    "webhooks": webhooks,
                },
            }

            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=3.0),
                headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"},
            ) as client:
                # Preferir PUT /api/sessions/{session} para actualizar la config
                put_url = (
                    f"{self.base_url.rstrip('/')}/api/sessions/{self.session_name}"
                )
                response = await client.put(put_url, json=session_payload)

                # Si PUT no está soportado, fallback a POST /api/sessions (create/update)
                if response.status_code == 404:
                    post_url = f"{self.base_url.rstrip('/')}/api/sessions"
                    response = await client.post(post_url, json=session_payload)

                data = self._handle_response(response)
                urls = ", ".join([w.get("url", "") for w in webhooks])
                logger.info(
                    f"WAHA session webhooks configurados para '{self.session_name}': {urls}"
                )
                return data
        except httpx.TimeoutException:
            raise WAHATimeoutError("Timeout configurando webhooks de WAHA")
        except httpx.HTTPError as e:
            raise WAHAConnectionError(f"Error configurando webhooks de WAHA: {str(e)}")

    @retry_on_failure(max_retries=3, delay=1.0)
    async def configure_webhook(
        self,
        url: str,
        enabled: bool = True,
        events: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Compatibilidad: configura un único webhook.
        """
        webhook_cfg: Dict[str, Any] = {"url": url}
        if events:
            webhook_cfg["events"] = events
        # `enabled` se mantiene por compatibilidad aunque WAHA solo use la lista `webhooks`.
        return await self.configure_webhooks([webhook_cfg])

    @retry_on_failure(max_retries=3, delay=1.0)
    async def start_session(self, session_name: Optional[str] = None) -> Dict[str, Any]:
        """Inicia la sesión de WAHA mediante POST /api/sessions/{session}/start.

        Args:
            session_name: Nombre de la sesión a iniciar. Si no se provee, usa `self.session_name`.

        Returns:
            Dict con el payload de respuesta de WAHA.

        Raises:
            WAHATimeoutError: Cuando WAHA no responde dentro del timeout.
            WAHAConnectionError: Cuando ocurre un error de conexión o servidor.
        """
        target_session = session_name or self.session_name
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=3.0),
                headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"},
            ) as client:
                url = f"{self.base_url.rstrip('/')}/api/sessions/{target_session}/start"
                response = await client.post(url)
                data = self._handle_response(response)
                logger.info(f"WAHA session '{target_session}' iniciada correctamente")
                return data
        except httpx.TimeoutException:
            raise WAHATimeoutError("Timeout iniciando sesión WAHA")
        except httpx.HTTPError as e:
            raise WAHAConnectionError(f"Error iniciando sesión WAHA: {str(e)}")


# Instancia global del cliente (se inicializa cuando se necesite)
_waha_client: Optional[WAHAClient] = None


async def _quick_ping(base_url: str, session_name: str = "default") -> bool:
    """
    Fast-check if WAHA service is reachable using short timeouts.

    Returns True if the server responds (any HTTP status), and False
    if a timeout or connection error occurs. Prevents blocking the
    global request when WAHA is unavailable.
    """
    try:
        url = f"{base_url.rstrip('/')}/api/sessions/{session_name}"
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=2.0),
            headers={"X-Api-Key": WAHA_API_KEY, "Content-Type": "application/json"},
        ) as client:
            _ = await client.get(url)
            return True
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
        return False


async def get_waha_client() -> WAHAClient:
    """
    Obtiene la instancia global del cliente WAHA

    Returns:
        Instancia del cliente WAHA
    """
    global _waha_client

    if _waha_client is None:
        # Intentar primero Docker (red interna), luego localhost, con ping rápido
        candidates = [
            ("http://waha:8000", "Docker"),
            ("http://localhost:3000", "localhost"),
        ]

        for base_url, label in candidates:
            if await _quick_ping(base_url, "default"):
                _waha_client = WAHAClient(base_url)
                logger.info(f"Conectado a WAHA via {label}")
                break

        if _waha_client is None:
            logger.error("WAHA no disponible en 'waha:8000' ni 'localhost:3000'")
            raise WAHAConnectionError("No se pudo establecer conexión con WAHA")

    return _waha_client


async def close_waha_client():
    """Cierra la instancia global del cliente WAHA"""
    global _waha_client
    if _waha_client:
        await _waha_client.close()
        _waha_client = None
        logger.info("Cliente WAHA global cerrado")
