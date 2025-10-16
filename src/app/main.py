from fastapi import FastAPI
from app.api.v1.translate import router as translate_router
from app.api.v1.health import router as health_router

app = FastAPI(title="Quichua Translator API")
app.include_router(translate_router, prefix="/v1/translate", tags=["translate"])
app.include_router(health_router, prefix="/health", tags=["health"])
