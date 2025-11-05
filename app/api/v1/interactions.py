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


@router.get(
    "/{phone}",
    response_model=InteractionResponse,
    response_model_exclude={"timeline"},
)
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
        if "timeline" not in interaction or interaction["timeline"] is None:
            interaction["timeline"] = []

        # Build summary from timeline and current route (ignoring route_1)
        interaction["summary"] = _build_interaction_summary(
            interaction.get("timeline", []), interaction.get("route")
        )

        return InteractionResponse(**interaction)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener interaction por phone: {str(e)}",
        )


def _build_interaction_summary(timeline: list, current_route: str | None) -> str:
    """Generate a human-readable paragraph summary based on timeline and route.

    Notes (English):
    - Ignore entries with route == 'route_1'.
    - Prefer the current interaction route if it is one of route_2/route_3/route_4.
    - Otherwise, select the most recent (last) route in the timeline among route_2/route_3/route_4.
    - Build a cohesive paragraph tailored to each route using available steps.
    """

    allowed_routes = {"route_2", "route_3", "route_4"}
    type_by_route = {
        "route_2": "abuso sexual",
        "route_3": "denuncia penal",
        "route_4": "deuda de alimentos",
    }

    # Choose target route
    target_route = None
    if current_route in allowed_routes:
        target_route = current_route
    else:
        for entry in reversed(timeline or []):
            r = (entry or {}).get("route")
            if r in allowed_routes:
                target_route = r
                break

    if not target_route:
        return "No hay información suficiente para generar el resumen."

    # Collect step -> userInput for the target route
    steps = {}
    for entry in timeline or []:
        if (entry or {}).get("route") != target_route:
            continue
        step_num = (entry or {}).get("step")
        user_input = (entry or {}).get("userInput")
        if step_num is None:
            continue
        steps[int(step_num)] = (user_input or "").strip()

    tipo = type_by_route.get(target_route, target_route)

    # Compose paragraph by route
    if target_route == "route_2":
        # abuso sexual
        s1 = steps.get(1)
        s2 = steps.get(2)
        s3 = steps.get(3)
        parts: list[str] = []
        parts.append(f"Tipo de denuncia: {tipo}.")
        if s1:
            parts.append(f"El usuario indicó que desea realizar una {s1}.")
        if s2:
            parts.append(f"La persona se identifica como {s2}.")
        if s3:
            parts.append(f"Información adicional: {s3}.")
        return " ".join(parts)

    if target_route == "route_3":
        # denuncia penal
        s1 = steps.get(1)
        s2 = steps.get(2)
        s3 = steps.get(3)
        s4 = steps.get(4)
        parts: list[str] = []
        parts.append(f"Tipo de denuncia: {tipo}.")
        if s1:
            parts.append(f"El usuario indicó que desea realizar una {s1}.")
        if s2:
            parts.append(f"La persona es {s2}.")
        if s3:
            parts.append(f"Tipo de delito: {s3}.")
        if s4:
            parts.append(f"Información adicional: {s4}.")
        return " ".join(parts)

    if target_route == "route_4":
        # deuda de alimentos
        s1 = steps.get(1)
        s2 = steps.get(2)
        s3 = steps.get(3)
        s4 = steps.get(4)
        parts: list[str] = []
        parts.append(f"Tipo de denuncia: {tipo}.")
        if s1:
            parts.append(f"El usuario indicó que desea realizar una {s1}.")
        if s2:
            parts.append(f"Responsable de los menores: {s2}.")
        if s3:
            parts.append(f"Sentencia existente: {s3}.")
        if s4:
            parts.append(f"Información adicional: {s4}.")
        return " ".join(parts)

    # Fallback (should not happen given allowed_routes)
    return "No hay información suficiente para generar el resumen."
