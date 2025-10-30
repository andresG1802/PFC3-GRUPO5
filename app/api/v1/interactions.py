"""
Interactions - Endpoints para gestión de interacciones
"""

from fastapi import APIRouter, HTTPException, Query, Path, status, Depends
from typing import Optional
from datetime import datetime
import logging

# Importar modelos desde el módulo centralizado
from ..models.interactions import (
    InteractionResponse,
    InteractionListResponse,
    AssignAsesorResponse,
)
from ...database.models import InteractionModel
from .auth import get_current_user

# Configurar router con tags a nivel de clase
router = APIRouter(tags=["Interactions"])

# Configurar logger
logger = logging.getLogger(__name__)


@router.get("", response_model=InteractionListResponse)
async def get_interactions(
    skip: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(
        10, ge=1, le=100, description="Número máximo de registros a retornar"
    ),
    state: Optional[str] = Query(
        None, description="Filtrar por estado de la interaction"
    ),
    current_asesor: dict = Depends(get_current_user),
):
    """
    Obtiene lista de interactions con paginación completa y filtro opcional por estado

    Args:
        skip: Número de registros a omitir
        limit: Número máximo de registros a retornar
        state: Estado opcional para filtrar interactions (ej: "menus", "active", "completed")
        current_asesor: Asesor autenticado (obtenido del token)

    Returns:
        InteractionListResponse: Lista paginada de interactions con metadatos completos
    """
    try:
        # Obtener el total de registros que coinciden con el filtro
        total = InteractionModel.count_all(state=state)

        # Obtener las interactions paginadas
        interactions = InteractionModel.find_all(skip=skip, limit=limit, state=state)

        # Convertir a formato de respuesta
        interaction_responses = []
        for interaction in interactions:
            try:
                # Asegurar que el campo id esté mapeado correctamente desde _id
                if "_id" in interaction:
                    interaction["id"] = interaction["_id"]
                
                # Validar que los campos requeridos estén presentes
                if "chat_id" not in interaction:
                    raise ValueError(f"Campo 'chat_id' faltante en interaction {interaction.get('_id', 'unknown')}")
                
                if "timeline" not in interaction or not interaction["timeline"]:
                    raise ValueError(f"Campo 'timeline' faltante o vacío en interaction {interaction.get('_id', 'unknown')}")
                
                # Validar que cada entrada del timeline tenga timestamp
                for i, entry in enumerate(interaction["timeline"]):
                    if "timestamp" not in entry:
                        raise ValueError(f"Campo 'timestamp' faltante en timeline[{i}] de interaction {interaction.get('_id', 'unknown')}")
                
                interaction_responses.append(InteractionResponse(**interaction))
            except Exception as e:
                logger.error(f"Error al procesar interaction {interaction.get('_id', 'unknown')}: {str(e)}")
                logger.error(f"Datos de la interaction: {interaction}")
                # Continuar con las demás interactions en lugar de fallar completamente
                continue

        # Calcular metadatos de paginación
        count = len(interaction_responses)
        page = (skip // limit) + 1 if limit > 0 else 1
        total_pages = (total + limit - 1) // limit if limit > 0 else 1
        has_next = skip + limit < total
        has_previous = skip > 0

        return InteractionListResponse(
            interactions=interaction_responses,
            total=total,
            count=count,
            skip=skip,
            limit=limit,
            has_next=has_next,
            has_previous=has_previous,
            page=page,
            total_pages=total_pages,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener interactions: {str(e)}",
        )


@router.get("/{interaction_id}", response_model=InteractionResponse)
async def get_interaction(
    interaction_id: str = Path(..., description="ID de la interaction"),
    current_asesor: dict = Depends(get_current_user),
):
    """
    Obtiene una interaction específica por ID

    Args:
        interaction_id: ID de la interaction
        current_asesor: Asesor autenticado (obtenido del token)

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
                detail="Interaction no encontrada",
            )

        # Asegurar que el campo id esté mapeado correctamente desde _id
        if "_id" in interaction:
            interaction["id"] = interaction["_id"]
        
        # Validar que los campos requeridos estén presentes
        if "chat_id" not in interaction:
            logger.error(f"Campo 'chat_id' faltante en interaction {interaction_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Datos de interaction incompletos: falta chat_id",
            )
        
        if "timeline" not in interaction or not interaction["timeline"]:
            logger.error(f"Campo 'timeline' faltante o vacío en interaction {interaction_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Datos de interaction incompletos: falta timeline",
            )
        
        # Validar que cada entrada del timeline tenga timestamp
        for i, entry in enumerate(interaction["timeline"]):
            if "timestamp" not in entry:
                logger.error(f"Campo 'timestamp' faltante en timeline[{i}] de interaction {interaction_id}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Datos de interaction incompletos: falta timestamp en timeline[{i}]",
                )

        return InteractionResponse(**interaction)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener interaction: {str(e)}",
        )


@router.post("/{interaction_id}/assign", response_model=AssignAsesorResponse)
async def assign_asesor_to_interaction(
    interaction_id: str = Path(..., description="ID de la interaction"),
    current_asesor: dict = Depends(get_current_user),
):
    """
    Asigna el asesor autenticado a una interaction específica

    Args:
        interaction_id: ID de la interaction a asignar
        current_asesor: Asesor autenticado (obtenido del token)

    Returns:
        AssignAsesorResponse: Confirmación de la asignación

    Raises:
        HTTPException: Si la interaction no existe o ya está asignada
    """
    try:
        # Verificar que la interaction existe
        existing_interaction = InteractionModel.find_by_id(interaction_id)
        if not existing_interaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interaction no encontrada",
            )

        # Verificar si ya está asignada a otro asesor
        if existing_interaction.get("asesor_id") and existing_interaction.get(
            "asesor_id"
        ) != str(current_asesor["_id"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Esta interaction ya está asignada a otro asesor",
            )

        # Verificar si ya está asignada al mismo asesor
        if existing_interaction.get("asesor_id") == str(current_asesor["_id"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Esta interaction ya está asignada a usted",
            )

        # Asignar el asesor a la interaction
        asesor_id = str(current_asesor["_id"])
        assigned = InteractionModel.assign_asesor(interaction_id, asesor_id)

        if not assigned:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al asignar asesor a la interaction",
            )

        return AssignAsesorResponse(
            message="Asesor asignado exitosamente a la interaction",
            interaction_id=interaction_id,
            asesor_id=asesor_id,
            assignedAt=datetime.utcnow(),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al asignar asesor: {str(e)}",
        )
