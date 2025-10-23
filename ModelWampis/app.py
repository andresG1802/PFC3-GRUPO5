
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import os, json, re, unicodedata, pathlib, time

APP_DIR = pathlib.Path(__file__).parent
GLOSS_PATH = APP_DIR / "glossary" / "glossary-wampis.json"

app = FastAPI(title="Model Wampís API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())

def load_glossary() -> List[Dict[str, str]]:
    if not GLOSS_PATH.exists():
        return []
    data = json.loads(GLOSS_PATH.read_text(encoding="utf-8"))
    pairs = data.get("pairs", [])
    cleaned = []
    for p in pairs:
        if not isinstance(p, dict): 
            continue
        es = p.get("es"); wa = p.get("wa")
        if isinstance(es, str) and isinstance(wa, str):
            cleaned.append({"es": es.strip(), "wa": wa.strip(), "categoria": p.get("categoria", "")})
    return cleaned

GLOSSARY = load_glossary()
GLOSS_UPDATED_AT = time.time()

def build_indexes(pairs: List[Dict[str, str]]):
    es2wa, wa2es = {}, {}
    for p in pairs:
        es = norm(p["es"]); wa = norm(p["wa"])
        es2wa[es] = wa; wa2es[wa] = es
        es2wa.setdefault(strip_accents(es), wa)
        wa2es.setdefault(strip_accents(wa), es)
    return es2wa, wa2es

ES2WA, WA2ES = build_indexes(GLOSSARY)

WORD_RE = re.compile(r"([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+|\d+|[^\w\s]+|\s+)", re.UNICODE)

def translate(text: str, direction: str, keep_unknown: bool = True):
    src2tgt = ES2WA if direction == "es->wa" else WA2ES
    full = norm(text)
    hit = src2tgt.get(full) or src2tgt.get(strip_accents(full))
    if hit:
        return hit, []

    tokens = WORD_RE.findall(text)
    unknown = []
    out_tokens: List[str] = []

    for tok in tokens:
        if tok.isspace() or re.fullmatch(r"[^\w\s]+", tok):
            out_tokens.append(tok); continue

        base = norm(tok)
        tr = src2tgt.get(base) or src2tgt.get(strip_accents(base))
        if tr is None:
            unknown.append(tok)
            out_tokens.append(tok if keep_unknown else f"‹{tok}›")
        else:
            if tok.isupper():
                out_tokens.append(tr.upper())
            elif tok.istitle():
                out_tokens.append(tr.capitalize())
            else:
                out_tokens.append(tr)
    return "".join(out_tokens), sorted(set(unknown))

def detect_direction(text: str):
    es_hits = sum(1 for k in ES2WA.keys() if k in norm(text) or k in strip_accents(norm(text)))
    wa_hits = sum(1 for k in WA2ES.keys() if k in norm(text) or k in strip_accents(norm(text)))
    return "es->wa" if es_hits >= wa_hits else "wa->es"

class TranslateIn(BaseModel):
    text: str
    direction: Optional[str] = None
    keep_unknown: Optional[bool] = True

class TranslateOut(BaseModel):
    input: str
    output: str
    direction: str
    unknown: List[str] = []
    glossary_version: float

@app.get("/health")
def health():
    return {"status":"ok","pairs":len(GLOSSARY),"updated_at":GLOSS_UPDATED_AT}

@app.post("/translate", response_model=TranslateOut)
def translate_route(payload: TranslateIn):
    if not payload.text.strip():
        raise HTTPException(400, "text vacío")
    direction = payload.direction or detect_direction(payload.text)
    if direction not in ("es->wa", "wa->es"):
        raise HTTPException(400, "direction inválida")
    out, unknown = translate(payload.text, direction, keep_unknown=payload.keep_unknown)
    return TranslateOut(
        input=payload.text, output=out, direction=direction,
        unknown=unknown, glossary_version=GLOSS_UPDATED_AT
    )

@app.post("/upload_glossary")
def upload_glossary(file: UploadFile = File(...)):
    if not file.filename.endswith(".json"):
        raise HTTPException(400, "Sube un JSON con {'pairs': [{'es':'...', 'wa':'...'}]}")
    raw = file.file.read().decode("utf-8")
    try:
        data = json.loads(raw)
        if "pairs" not in data or not isinstance(data["pairs"], list):
            raise ValueError("Estructura inválida")
    except Exception as e:
        raise HTTPException(400, f"JSON inválido: {e}")
    GLOSS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _reload()
    return {"status":"ok","pairs":len(GLOSSARY)}

@app.post("/reload")
def reload_route():
    _reload()
    return {"status":"ok","pairs":len(GLOSSARY)}

def _reload():
    global GLOSSARY, ES2WA, WA2ES, GLOSS_UPDATED_AT
    GLOSSARY = load_glossary()
    ES2WA, WA2ES = build_indexes(GLOSSARY)
    GLOSS_UPDATED_AT = time.time()
