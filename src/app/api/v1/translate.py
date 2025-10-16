from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.model_loader import Translator

router = APIRouter()
# Cargamos el modelo al iniciar la APP
translator = Translator()

class TranslateRequest(BaseModel):
    text: str
    src: str = "spa_Latn"
    tgt: str = "quz_Latn"
    num_beams: int = 4

class TranslateResponse(BaseModel):
    translation: str

@router.post("/", response_model=TranslateResponse)
async def translate(req: TranslateRequest):
    if not req.text:
        raise HTTPException(status_code=400, detail="text is required")
    result = translator.translate(req.text, src_lang=req.src, tgt_lang=req.tgt, num_beams=req.num_beams)
    return {"translation": result}
