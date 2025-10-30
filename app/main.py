from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1.auth import router as auth_router
from .api.v1.health import router as health_router
from .api.v1.interactions import router as interactions_router
from .api.v1.chats import router as chats_router
from .api.v1.webhooks import router as webhooks_router
from .api.v1.presence import router as presence_router
from .database.connection import get_database, close_database_connection
from .database.seeder import seed_database
from .services.waha_client import close_waha_client
from .utils.logging_config import init_logging
from .config.security import rate_limit_config
from .middleware import (
    ErrorHandlerMiddleware,
    TimeoutMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    RateLimitingMiddleware,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestión del ciclo de vida de la aplicación
    """
    # Startup
    print("Starting Backend API...")

    # Inicializar logging
    init_logging()

    print("Connecting to MongoDB...")
    get_database()  # Inicializar conexión a la base de datos

    # Ejecutar seeder para poblar la base de datos
    try:
        seed_database()
    except Exception as e:
        print(f"Error durante el seeding: {e}")

    yield
    # Shutdown
    print("Closing database connections...")
    close_database_connection()
    print("Closing WAHA client...")
    await close_waha_client()
    print("API successfully shutdown")


# Crear aplicación FastAPI
app = FastAPI(
    title="ARU-LINK WhatsApp API",
    description="API Backend para Aru-Link",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={"name": "ARU-LINK Team", "email": "support@aru-link.com"},
    license_info={"name": "MIT License", "url": "https://opensource.org/licenses/MIT"},
    servers=[
        {"url": "http://localhost:8000", "description": "Servidor de desarrollo"},
        {"url": "https://api.aru-link.com", "description": "Servidor de producción"},
    ],
)

# Configurar middlewares (orden importante: primero los de seguridad)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middlewares de manejo de errores y timeout
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(TimeoutMiddleware, timeout_seconds=30.0)
# Remover el middleware de rate limiting antiguo ya que usamos el nuevo
# app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

# Incluir routers
app.include_router(auth_router, prefix="/auth")
app.include_router(health_router, prefix="/health")
app.include_router(interactions_router, prefix="/api/v1/interactions")
app.include_router(chats_router, prefix="/api/v1/chats")
app.include_router(webhooks_router, prefix="/api/v1/webhooks")
app.include_router(presence_router, prefix="/api/v1/presence")

if __name__ == "__main__":
    import uvicorn
    from .api.envs import HOST, PORT

    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="info")
