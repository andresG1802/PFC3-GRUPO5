from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .api.v1.auth import router as auth_router
from .api.v1.health import router as health_router
from .api.v1.interactions import router as interactions_router
from .middleware import SecurityHeadersMiddleware

from .api.envs import HOST, PORT, DEBUG
from .database import close_database_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestión del ciclo de vida de la aplicación
    """
    # Startup
    print("Starting Backend API...")
    print("Connecting to MongoDB...")
    yield
    # Shutdown
    print("Closing database connections...")
    close_database_connection()
    print("API successfully shutdown")


# Crear aplicación FastAPI
app = FastAPI(
    title="ARU-LINK API Docs",
    description="Backend API con arquitectura modular para el proyecto ARU-LINK",
    version="0.0.1",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Agregar middleware de seguridad (debe ir después de CORS)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth_router, prefix="/auth")
app.include_router(health_router, prefix="/health")
app.include_router(interactions_router, prefix="/interactions")

if __name__ == "__main__":
    import uvicorn

    if DEBUG:
        uvicorn.run("main:app", host=HOST, port=PORT, reload=DEBUG, log_level="info")
    else:
        uvicorn.run("main:app", host=HOST, port=PORT, log_level="info")
