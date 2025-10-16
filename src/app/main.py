from fastapi import FastAPI
from app.api.v1.translate import router as translate_router
from app.api.v1.health import router as health_router
from app.core.model_loader import Translator

app = FastAPI(title="Quichua Translator API")

@app.on_event("startup")
def startup_event():
    # Cargar el modelo una única vez al arrancar la app (no en import-time)
    # Puedes pasar use_8bit=True sólo si tienes bitsandbytes configurado.
    app.state.translator = Translator()

app.include_router(translate_router, prefix="/v1/translate", tags=["translate"])
app.include_router(health_router, prefix="/health", tags=["health"])