"""
Interactions - Endpoints para gestión de interacciones
"""

from fastapi import APIRouter, HTTPException, Query, Path, status
from typing import List
from datetime import datetime

# Importar modelos desde el módulo centralizado
from ..models.interactions import (
    InteractionCreate, 
    InteractionUpdate, 
    InteractionResponse,
    InteractionListResponse,
    TimelineEntry
)
from ...database.models import InteractionModel

# Configurar router con tags a nivel de clase
router = APIRouter(tags=["Interactions"])


@router.post("/", response_model=InteractionResponse, status_code=status.HTTP_201_CREATED)
async def create_interaction(interaction: InteractionCreate):
    """
    Crea una nueva interaction

    Args:
        interaction: Datos de la interaction a crear

    Returns:
        InteractionResponse: Interaction creada

    Raises:
        HTTPException: Si ya existe una interaction con el mismo teléfono
    """
    try:
        # Verificar si ya existe una interaction con este teléfono
        existing = InteractionModel.find_by_phone(interaction.phone)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe una interaction para el teléfono {interaction.phone}"
            )
        
        # Preparar datos para inserción
        interaction_data = interaction.model_dump()
        
        # Crear la interaction
        interaction_id = InteractionModel.create(interaction_data)
        
        # Obtener la interaction creada
        created_interaction = InteractionModel.find_by_id(interaction_id)
        if not created_interaction:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al crear la interaction"
            )
        
        return InteractionResponse(**created_interaction)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )


@router.get("/", response_model=InteractionListResponse)
async def get_interactions(
    skip: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a retornar")
):
    """
    Obtiene lista de interactions con paginación

    Args:
        skip: Número de registros a omitir
        limit: Número máximo de registros a retornar

    Returns:
        InteractionListResponse: Lista paginada de interactions
    """
    try:
        interactions = InteractionModel.find_all(skip=skip, limit=limit)
        
        # Convertir a formato de respuesta
        interaction_responses = [
            InteractionResponse(**interaction) for interaction in interactions
        ]
        
        return InteractionListResponse(
            interactions=interaction_responses,
            total=len(interaction_responses),
            skip=skip,
            limit=limit
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener interactions: {str(e)}"
        )


@router.get("/{interaction_id}", response_model=InteractionResponse)
async def get_interaction(
    interaction_id: str = Path(..., description="ID de la interaction")
):
    """
    Obtiene una interaction específica por ID

    Args:
        interaction_id: ID de la interaction

    Returns:
        InteractionResponse: Datos de la interaction

    Raises:
        HTTPException: Si la interaction no existe
    """
    try:
        interaction = InteractionModel.find_by_id(interaction_id)
        
        if not interaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interaction no encontrada"
            )
        
        return InteractionResponse(**interaction)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener interaction: {str(e)}"
        )


@router.get("/phone/{phone}", response_model=InteractionResponse)
async def get_interaction_by_phone(
    phone: str = Path(..., description="Número de teléfono")
):
    """
    Obtiene una interaction por número de teléfono

    Args:
        phone: Número de teléfono

    Returns:
        InteractionResponse: Datos de la interaction

    Raises:
        HTTPException: Si la interaction no existe
    """
    try:
        interaction = InteractionModel.find_by_phone(phone)
        
        if not interaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró interaction para el teléfono {phone}"
            )
        
        return InteractionResponse(**interaction)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener interaction: {str(e)}"
        )


@router.put("/{interaction_id}", response_model=InteractionResponse)
async def update_interaction(
    interaction_id: str = Path(..., description="ID de la interaction"),
    interaction_update: InteractionUpdate = None
):
    """
    Actualiza una interaction existente

    Args:
        interaction_id: ID de la interaction
        interaction_update: Datos a actualizar

    Returns:
        InteractionResponse: Interaction actualizada

    Raises:
        HTTPException: Si la interaction no existe
    """
    try:
        # Verificar que la interaction existe
        existing_interaction = InteractionModel.find_by_id(interaction_id)
        if not existing_interaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interaction no encontrada"
            )
        
        # Preparar datos de actualización (solo campos no nulos)
        update_data = {}
        if interaction_update.state is not None:
            update_data["state"] = interaction_update.state
        if interaction_update.route is not None:
            update_data["route"] = interaction_update.route
        if interaction_update.step is not None:
            update_data["step"] = interaction_update.step
        if interaction_update.lang is not None:
            update_data["lang"] = interaction_update.lang
        if interaction_update.timeline is not None:
            update_data["timeline"] = [entry.model_dump() for entry in interaction_update.timeline]
        
        # Actualizar interaction
        updated = InteractionModel.update_by_id(interaction_id, update_data)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al actualizar interaction"
            )
        
        # Obtener interaction actualizada
        updated_interaction = InteractionModel.find_by_id(interaction_id)
        return InteractionResponse(**updated_interaction)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar interaction: {str(e)}"
        )


@router.put("/phone/{phone}", response_model=InteractionResponse)
async def update_interaction_by_phone(
    phone: str = Path(..., description="Número de teléfono"),
    interaction_update: InteractionUpdate = None
):
    """
    Actualiza una interaction por número de teléfono

    Args:
        phone: Número de teléfono
        interaction_update: Datos a actualizar

    Returns:
        InteractionResponse: Interaction actualizada

    Raises:
        HTTPException: Si la interaction no existe
    """
    try:
        # Verificar que la interaction existe
        existing_interaction = InteractionModel.find_by_phone(phone)
        if not existing_interaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró interaction para el teléfono {phone}"
            )
        
        # Preparar datos de actualización (solo campos no nulos)
        update_data = {}
        if interaction_update.state is not None:
            update_data["state"] = interaction_update.state
        if interaction_update.route is not None:
            update_data["route"] = interaction_update.route
        if interaction_update.step is not None:
            update_data["step"] = interaction_update.step
        if interaction_update.lang is not None:
            update_data["lang"] = interaction_update.lang
        if interaction_update.timeline is not None:
            update_data["timeline"] = [entry.model_dump() for entry in interaction_update.timeline]
        
        # Actualizar interaction
        updated = InteractionModel.update_by_phone(phone, update_data)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al actualizar interaction"
            )
        
        # Obtener interaction actualizada
        updated_interaction = InteractionModel.find_by_phone(phone)
        return InteractionResponse(**updated_interaction)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar interaction: {str(e)}"
        )


@router.delete("/{interaction_id}")
async def delete_interaction(
    interaction_id: str = Path(..., description="ID de la interaction")
):
    """
    Elimina una interaction

    Args:
        interaction_id: ID de la interaction

    Returns:
        dict: Mensaje de confirmación

    Raises:
        HTTPException: Si la interaction no existe
    """
    try:
        # Verificar que la interaction existe
        existing_interaction = InteractionModel.find_by_id(interaction_id)
        if not existing_interaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interaction no encontrada"
            )
        
        # Eliminar interaction
        deleted = InteractionModel.delete_by_id(interaction_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al eliminar interaction"
            )
        
        return {
            "message": f"Interaction para teléfono {existing_interaction['phone']} eliminada correctamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar interaction: {str(e)}"
        )


@router.delete("/phone/{phone}")
async def delete_interaction_by_phone(
    phone: str = Path(..., description="Número de teléfono")
):
    """
    Elimina una interaction por número de teléfono

    Args:
        phone: Número de teléfono

    Returns:
        dict: Mensaje de confirmación

    Raises:
        HTTPException: Si la interaction no existe
    """
    try:
        # Verificar que la interaction existe
        existing_interaction = InteractionModel.find_by_phone(phone)
        if not existing_interaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró interaction para el teléfono {phone}"
            )
        
        # Eliminar interaction
        deleted = InteractionModel.delete_by_phone(phone)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al eliminar interaction"
            )
        
        return {
            "message": f"Interaction para teléfono {phone} eliminada correctamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar interaction: {str(e)}"
        )