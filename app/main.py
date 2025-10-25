from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .api.v1.auth import router as auth_router
from .api.v1.users import router as users_router
from .api.v1.health import router as health_router
from .api.v1.system import router as system_router

from .api.envs import HOST, PORT, DEBUG


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestión del ciclo de vida de la aplicación
    """
    # Startup
    print("Starting Backend API...")
    yield
    # Shutdown
    print("API succesfully shutdown")


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

app.include_router(auth_router, prefix="/auth")
app.include_router(users_router, prefix="/users")
app.include_router(health_router, prefix="/health")
app.include_router(system_router, prefix="/system")

if __name__ == "__main__":
    import uvicorn

    if DEBUG:
        uvicorn.run("main:app", host=HOST, port=PORT, reload=DEBUG, log_level="info")
    else:
        uvicorn.run("main:app", host=HOST, port=PORT, log_level="info")
