"""
Interactions - Endpoints para gestión de interacciones
"""

from fastapi import APIRouter, HTTPException, Path, status, Depends
import logging

# Importar modelos desde el módulo centralizado
from ..models.interactions import InteractionResponse
from ...database.models import InteractionModel
from .auth import get_current_user

# Configurar router con tags a nivel de clase
router = APIRouter(tags=["Interactions"])

# Configurar logger
logger = logging.getLogger(__name__)


@router.get("/{phone}", response_model=InteractionResponse)
async def get_interaction_by_phone(
    phone: str = Path(..., description="Número de teléfono (WA ID)"),
    current_asesor: dict = Depends(get_current_user),
):
    """
    Get a single interaction by phone only if it is in 'pending' state.

    Args:
        phone: Phone identifier stored on interaction (e.g. "51948604478@c.us").
        current_asesor: Authenticated advisor from token.

    Returns:
        InteractionResponse: Full interaction data when pending.

    Raises:
        HTTPException 404: Interaction not found or not in pending state.
    """
    try:
        interaction = InteractionModel.find_by_phone(phone)

        if not interaction or interaction.get("state") != "pending":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interaction no encontrada o no está en estado pending",
            )

        # Map id from _id
        if "_id" in interaction:
            interaction["id"] = interaction["_id"]

        # Ensure chat_id is present (fallback to phone)
        if not interaction.get("chat_id"):
            interaction["chat_id"] = phone

        # Ensure timeline exists (default empty list)
        if "timeline" not in interaction:
            interaction["timeline"] = []

        return InteractionResponse(**interaction)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener interaction por phone: {str(e)}",
        )
