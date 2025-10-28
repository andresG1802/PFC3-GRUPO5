"""
Modelos de base de datos para MongoDB
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel
from .connection import get_interactions_collection, get_asesores_collection


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
        
        # Agregar timestamp de creación
        interaction_data["createdAt"] = datetime.utcnow()
        
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
    def find_all(skip: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene todas las interactions con paginación
        
        Args:
            skip: Número de registros a omitir
            limit: Número máximo de registros
            
        Returns:
            List: Lista de interactions
        """
        collection = get_interactions_collection()
        
        cursor = collection.find().skip(skip).limit(limit).sort("createdAt", -1)
        results = []
        
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(doc)
            
        return results
    
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
                {"_id": ObjectId(interaction_id)},
                {"$set": update_data}
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
        
        result = collection.update_one(
            {"phone": phone},
            {"$set": update_data}
        )
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


class AsesorModel:
    """Modelo para manejar asesores en MongoDB"""
    
    @staticmethod
    def create_asesor(email: str, password: str, full_name: str):
        """Crea un nuevo asesor en la base de datos"""
        collection = get_asesores_collection()
        asesor_data = {
            "email": email,
            "password": password,
            "full_name": full_name,
            "is_active": True,
            "createdAt": datetime.utcnow()
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
        return collection.update_one(
            {"email": email},
            {"$set": update_data}
        )