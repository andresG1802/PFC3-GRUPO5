from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.envs.env import WAHA_BACKEND_WEBHOOK_URL
from .api.v1.auth import router as auth_router
from .api.v1.chats import router as chats_router
from .api.v1.health import router as health_router
from .api.v1.webhooks import router as webhooks_router
from .database.connection import close_database_connection, get_database
from .database.seeder import seed_database
from .middleware import (ErrorHandlerMiddleware, RateLimitingMiddleware,
                         SecurityHeadersMiddleware, TimeoutMiddleware)
from .services.waha_client import close_waha_client
from .utils.logging_config import init_logging


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

    # Configure WAHA webhook to deliver incoming WhatsApp events to our backend
    try:
        from .services.waha_client import get_waha_client

        waha_client = await get_waha_client()
        webhook_url = WAHA_BACKEND_WEBHOOK_URL
        await waha_client.configure_webhook(
            webhook_url,
            enabled=True,
            events=["message", "message.ack"],
        )
        print(f"WAHA webhook configured: {webhook_url}")
    except Exception as e:
        print(f"WAHA webhook configuration skipped: {e}")

    yield
    # Shutdown
    print("Closing database connections...")
    close_database_connection()
    print("Closing WAHA client...")
    await close_waha_client()
    print("API successfully shutdown")


app = FastAPI(
    title="ARU-LINK WhatsApp API",
    description="API Backend para Aru-Link",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={"name": "ARU-LINK Team", "email": "support@aru-link.com"},
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

# Incluir routers
app.include_router(auth_router, prefix="/auth")
app.include_router(health_router, prefix="/health")
app.include_router(chats_router, prefix="/api/v1/chats")
app.include_router(webhooks_router, prefix="/api/v1/webhooks")

if __name__ == "__main__":
    import uvicorn

    from .api.envs import HOST, PORT

    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        log_level="info",
        server_header=False,
        date_header=False,
    )
