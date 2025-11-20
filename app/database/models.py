"""
Modelos de base de datos para MongoDB
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pydantic import BaseModel

from .connection import (
    get_asesores_collection,
    get_chats_collection,
    get_interactions_collection,
)


class TimelineEntry(BaseModel):
    """Modelo para entradas del timeline"""

    route: Optional[str] = None
    step: Optional[int] = None
    userInput: Optional[str] = None


class InteractionModel:
    """Modelo para gestionar interactions en MongoDB"""

    @staticmethod
    def create(interaction_data: Dict[str, Any]) -> str:
        """
        Crea una nueva interaction

        Args:
            interaction_data: Datos de la interaction

        Returns:
            str: ID de la interaction creada
        """
        collection = get_interactions_collection()

        # Agregar timestamp de creación (timezone-aware UTC)
        interaction_data["createdAt"] = datetime.now(timezone.utc)

        result = collection.insert_one(interaction_data)
        return str(result.inserted_id)

    @staticmethod
    def find_by_id(interaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca una interaction por ID

        Args:
            interaction_id: ID de la interaction

        Returns:
            Dict o None: Datos de la interaction
        """
        collection = get_interactions_collection()

        try:
            result = collection.find_one({"_id": ObjectId(interaction_id)})
            if result:
                result["_id"] = str(result["_id"])
            return result
        except Exception:
            return None

    @staticmethod
    def find_by_phone(phone: str) -> Optional[Dict[str, Any]]:
        """
        Busca una interaction por número de teléfono

        Args:
            phone: Número de teléfono

        Returns:
            Dict o None: Datos de la interaction
        """
        collection = get_interactions_collection()

        result = collection.find_one({"phone": phone})
        if result:
            result["_id"] = str(result["_id"])
        return result

    @staticmethod
    def find_by_chat_id(chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca una interaction por chat_id

        Args:
            chat_id: ID del chat

        Returns:
            Dict o None: Datos de la interaction
        """
        collection = get_interactions_collection()

        result = collection.find_one({"chat_id": chat_id})
        if result:
            result["_id"] = str(result["_id"])
        return result

    @staticmethod
    def find_all(
        skip: int = 0, limit: int = 10, state: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtiene todas las interactions con paginación y filtro opcional por estado

        Args:
            skip: Número de registros a omitir
            limit: Número máximo de registros
            state: Estado opcional para filtrar interactions

        Returns:
            List: Lista de interactions
        """
        collection = get_interactions_collection()

        # Construir filtro
        filter_query = {}
        if state:
            filter_query["state"] = state

        cursor = (
            collection.find(filter_query).skip(skip).limit(limit).sort("createdAt", -1)
        )
        results = []

        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(doc)

        return results

    @staticmethod
    def count_all(state: Optional[str] = None) -> int:
        """
        Cuenta el total de interactions con filtro opcional por estado

        Args:
            state: Estado opcional para filtrar interactions

        Returns:
            int: Número total de interactions que coinciden con el filtro
        """
        collection = get_interactions_collection()

        # Construir filtro
        filter_query = {}
        if state:
            filter_query["state"] = state

        return collection.count_documents(filter_query)

    @staticmethod
    def update_by_id(interaction_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Actualiza una interaction por ID

        Args:
            interaction_id: ID de la interaction
            update_data: Datos a actualizar

        Returns:
            bool: True si se actualizó correctamente
        """
        collection = get_interactions_collection()

        try:
            result = collection.update_one(
                {"_id": ObjectId(interaction_id)}, {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception:
            return False

    @staticmethod
    def update_by_phone(phone: str, update_data: Dict[str, Any]) -> bool:
        """
        Actualiza una interaction por número de teléfono

        Args:
            phone: Número de teléfono
            update_data: Datos a actualizar

        Returns:
            bool: True si se actualizó correctamente
        """
        collection = get_interactions_collection()

        result = collection.update_one({"phone": phone}, {"$set": update_data})
        return result.modified_count > 0

    @staticmethod
    def delete_by_id(interaction_id: str) -> bool:
        """
        Elimina una interaction por ID

        Args:
            interaction_id: ID de la interaction

        Returns:
            bool: True si se eliminó correctamente
        """
        collection = get_interactions_collection()

        try:
            result = collection.delete_one({"_id": ObjectId(interaction_id)})
            return result.deleted_count > 0
        except Exception:
            return False

    @staticmethod
    def assign_asesor(interaction_id: str, asesor_id: str) -> bool:
        """
        Asigna un asesor a una interaction

        Args:
            interaction_id: ID de la interaction
            asesor_id: ID del asesor a asignar

        Returns:
            bool: True si se asignó correctamente
        """
        collection = get_interactions_collection()

        try:
            result = collection.update_one(
                {"_id": ObjectId(interaction_id)},
                {"$set": {"asesor_id": asesor_id, "assignedAt": timezone.utcnow()}},
            )
            return result.modified_count > 0
        except Exception:
            return False

    @staticmethod
    def find_by_asesor(
        asesor_id: str, skip: int = 0, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Obtiene interactions asignadas a un asesor específico

        Args:
            asesor_id: ID del asesor
            skip: Número de registros a omitir
            limit: Número máximo de registros

        Returns:
            List: Lista de interactions del asesor
        """
        collection = get_interactions_collection()

        cursor = (
            collection.find({"asesor_id": asesor_id})
            .skip(skip)
            .limit(limit)
            .sort("createdAt", -1)
        )
        results = []

        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(doc)

        return results

    @staticmethod
    def count_by_asesor(asesor_id: str, state: Optional[str] = None) -> int:
        """
        Cuenta cuántas interactions están asignadas a un asesor.

        Args:
            asesor_id: ID del asesor
            state: Estado opcional para filtrar (e.g., 'derived')

        Returns:
            int: Número de interactions del asesor
        """
        collection = get_interactions_collection()
        query: Dict[str, Any] = {"asesor_id": asesor_id}
        if state:
            query["state"] = state
        try:
            return collection.count_documents(query)
        except Exception:
            return 0

    @staticmethod
    def delete_by_phone(phone: str) -> bool:
        """
        Elimina una interaction por número de teléfono

        Args:
            phone: Número de teléfono

        Returns:
            bool: True si se eliminó correctamente
        """
        collection = get_interactions_collection()

        result = collection.delete_one({"phone": phone})
        return result.deleted_count > 0


class ChatModel:
    """Modelo para gestionar chats y sus mensajes en MongoDB"""

    @staticmethod
    def upsert_chat(chat_id: str, interaction_id: Optional[str] = None) -> bool:
        """
        Crea o actualiza el documento base del chat.

        Args:
            chat_id: ID único del chat (WA ID)
            interaction_id: ID de la interaction asociada

        Returns:
            bool: True si se modificó o creó el documento
        """
        collection = get_chats_collection()
        update = {"$set": {"chat_id": chat_id}}
        if interaction_id:
            update["$set"]["interaction_id"] = interaction_id
        update["$setOnInsert"] = {"createdAt": datetime.now(timezone.utc)}

        result = collection.update_one({"_id": chat_id}, update, upsert=True)
        return (result.upserted_id is not None) or (result.modified_count > 0)

    @staticmethod
    def add_message(
        chat_id: str,
        message: Dict[str, Any],
        interaction_id: Optional[str] = None,
    ) -> bool:
        """
        Agrega un mensaje al historial del chat (persistencia).

        Args:
            chat_id: ID del chat
            message: Datos del mensaje normalizados
            interaction_id: ID de la interaction asociada (opcional)

        Returns:
            bool: True si se insertó el mensaje
        """
        collection = get_chats_collection()

        # Asegurar documento de chat
        ChatModel.upsert_chat(chat_id, interaction_id)

        # Estructura básica del mensaje
        normalized = {
            "id": message.get("id"),
            "body": message.get("body"),
            "timestamp": message.get(
                "timestamp", int(datetime.now(timezone.utc).timestamp())
            ),
            "type": message.get("type", "text"),
            "from_me": bool(message.get("from_me", False)),
            "ack": message.get("ack"),
            "metadata": message.get("metadata"),
        }

        # Datos adicionales comunes
        if "advisor_id" in message:
            normalized["advisor_id"] = message["advisor_id"]
        if "from" in message:
            normalized["from"] = message["from"]

        result = collection.update_one(
            {"_id": chat_id}, {"$push": {"messages": normalized}}
        )
        return result.modified_count > 0

    @staticmethod
    def get_messages(chat_id: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """
        Obtiene mensajes persistidos de un chat con paginación simple.

        Args:
            chat_id: ID del chat
            limit: Máximo de mensajes
            offset: Desplazamiento de inicio

        Returns:
            Dict con mensajes y total
        """
        collection = get_chats_collection()
        doc = collection.find_one({"_id": chat_id}, {"messages": 1})
        messages = doc.get("messages", []) if doc else []

        total = len(messages)
        # Ordenar por timestamp descendente (más recientes primero)
        messages_sorted = sorted(
            messages, key=lambda m: m.get("timestamp", 0), reverse=True
        )
        paginated = messages_sorted[offset : offset + limit]

        return {"messages": paginated, "total": total}

    @staticmethod
    def get_chat(db_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un chat persistido desde MongoDB y construye datos mínimos.

        Devuelve un dict con campos compatibles con el modelo `Chat` del API:
        - id
        - name (si se puede inferir del teléfono de la interaction)
        - type (individual)
        - timestamp (último mensaje si existe)
        - unread_count (0 por defecto)
        - archived, pinned, muted (False)
        - last_message (si hay mensajes)

        Args:
            chat_id: ID del chat

        Returns:
            Dict o None: Datos del chat normalizados o None si no existe
        """
        collection = get_chats_collection()
        doc = collection.find_one({"_id": db_id})
        if not doc:
            return None

        # Intentar enriquecer con la interaction asociada (para nombre)
        interaction = InteractionModel.find_by_chat_id(db_id)
        name = None
        if interaction:
            name = interaction.get("phone")

        # Calcular último mensaje
        messages = doc.get("messages", [])
        last_msg = None
        timestamp = None
        if messages:
            messages_sorted = sorted(
                messages, key=lambda m: m.get("timestamp", 0), reverse=True
            )
            last_msg = messages_sorted[0]
            timestamp = last_msg.get("timestamp")

        chat_data: Dict[str, Any] = {
            "id": db_id,
            "name": name,
            "type": "individual",
            "timestamp": timestamp,
            "unread_count": 0,
            "archived": False,
            "pinned": False,
            "muted": False,
        }

        if last_msg:
            chat_data["last_message"] = {
                "id": last_msg.get("id") or "",
                "timestamp": last_msg.get("timestamp", 0),
                "from_me": bool(last_msg.get("from_me", False)),
                "type": last_msg.get("type", "text"),
                "body": last_msg.get("body"),
                "ack": last_msg.get("ack"),
            }

        return chat_data


class AsesorModel:
    """Modelo para manejar asesores en MongoDB"""

    @staticmethod
    def create_asesor(email: str, password: str, full_name: str, role: str = "asesor"):
        """Crea un nuevo asesor en la base de datos"""
        collection = get_asesores_collection()
        asesor_data = {
            "email": email,
            "password": password,
            "full_name": full_name,
            "role": role,  # Nuevo campo: "admin" o "asesor"
            "is_active": True,
            "createdAt": datetime.now(timezone.utc),
        }
        result = collection.insert_one(asesor_data)
        return result.inserted_id

    @staticmethod
    def find_by_email(email: str):
        """Busca un asesor por email"""
        collection = get_asesores_collection()
        return collection.find_one({"email": email})

    @staticmethod
    def find_by_id(asesor_id: str):
        """Busca un asesor por ID"""
        collection = get_asesores_collection()
        return collection.find_one({"_id": ObjectId(asesor_id)})

    @staticmethod
    def update_by_email(email: str, update_data: dict):
        """Actualiza un asesor por email"""
        collection = get_asesores_collection()
        return collection.update_one({"email": email}, {"$set": update_data})
