from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()

class TranslateRequest(BaseModel):
    text: str
    src: str = "spa_Latn"
    tgt: str = "quz_Latn"
    num_beams: int = 4

class TranslateResponse(BaseModel):
    translation: str

@router.post("/", response_model=TranslateResponse)
async def translate(req: TranslateRequest, request: Request):
    if not req.text:
        raise HTTPException(status_code=400, detail="text is required")

    translator = getattr(request.app.state, "translator", None)
    if translator is None:
        raise HTTPException(status_code=503, detail="Translator not loaded yet")

    result = translator.translate(req.text, src_lang=req.src, tgt_lang=req.tgt, num_beams=req.num_beams)
    return {"translation": result}
