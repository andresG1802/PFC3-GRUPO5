from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.app.utils.wampis_service import translate_text, detect_direction

router = APIRouter(prefix="/wampis", tags=["Wampís"])

class TranslateIn(BaseModel):
    text: str
    direction: str | None = None  # "es->wa" o "wa->es"
    keep_unknown: bool = True
    use_llm: bool = False

class TranslateOut(BaseModel):
    input: str
    output: str
    direction: str
    unknown: list[str] = []
    refined: bool = False
    glossary_version: float

@router.post("/translate", response_model=TranslateOut)
async def translate(payload: TranslateIn):
    if not payload.text.strip():
        raise HTTPException(400, "Texto vacío")

    direction = payload.direction or detect_direction(payload.text)
    if direction not in ("es->wa", "wa->es"):
        raise HTTPException(400, "Dirección inválida")

    output, unknown = translate_text(payload.text, direction, keep_unknown=payload.keep_unknown)

    return TranslateOut(
        input=payload.text,
        output=output,
        direction=direction,
        unknown=unknown,
        refined=False,
        glossary_version=1.0
    )