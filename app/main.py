import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.envs.env import DEBUG, WAHA_BACKEND_WEBHOOK_URL
from .api.v1.auth import router as auth_router
from .api.v1.chats import router as chats_router
from .api.v1.health import router as health_router
from .api.v1.webhooks import router as webhooks_router
from .database.connection import close_database_connection, get_database
from .database.seeder import seed_database
from .middleware import (ErrorHandlerMiddleware, RateLimitingMiddleware,
                         SecurityHeadersMiddleware, TimeoutMiddleware)
from .services.waha_client import close_waha_client
from .utils.logging_config import get_logger, init_logging

logger = get_logger(__name__)


ACTIVE_WAHA_STATUSES = {"WORKING", "STARTED", "CONNECTED", "INITIALIZED", "READY"}


async def _waha_supervisor(app: FastAPI, interval_seconds: int = 30) -> None:
    """Periodically ensure WAHA is reachable, session is active, and webhooks are set.

    This keeps the worker properly configured after WAHA restarts.
    """
    # Local import to avoid circular deps on app import time
    from .services.waha_client import _quick_ping, get_waha_client

    while True:
        try:
            waha_client = await get_waha_client()

            reachable = await _quick_ping(
                waha_client.base_url, waha_client.session_name
            )
            if not reachable:
                logger.warning("WAHA unreachable; supervisor will retry later")
            else:
                status_payload = await waha_client.get_session_status()
                status = str(status_payload.get("status", "")).upper()
                if status not in ACTIVE_WAHA_STATUSES:
                    await waha_client.start_session()

                # Idempotent webhook apply: safe to call repeatedly
                backend_webhook = {
                    "url": WAHA_BACKEND_WEBHOOK_URL,
                    "events": ["message", "message.ack"],
                }
                await waha_client.configure_webhooks([backend_webhook])
        except Exception as e:
            logger.warning(f"WAHA supervisor encountered an error: {e}")

        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestión del ciclo de vida de la aplicación
    """
    # Startup
    logger.info("Starting Backend API...")

    # Inicializar logging
    init_logging()

    logger.info("Connecting to MongoDB...")
    get_database()  # Inicializar conexión a la base de datos

    # Ejecutar seeder para poblar la base de datos
    try:
        seed_database()
    except Exception as e:
        logger.error(f"Error during seeding: {e}")

    # Configure WAHA webhooks: backend
    try:
        from .services.waha_client import get_waha_client

        waha_client = await get_waha_client()

        # Backend webhook
        backend_webhook = {
            "url": WAHA_BACKEND_WEBHOOK_URL,
            "events": ["message", "message.ack"],
        }
        await waha_client.configure_webhooks([backend_webhook])
        logger.info("WAHA webhook configured: backend only")

        # Start WAHA 'default' session once ready
        try:
            await waha_client.start_session()
            logger.info("WAHA session 'default' started")
        except Exception as e:
            logger.error(f"Failed to start WAHA session 'default': {e}")
    except Exception as e:
        logger.error(f"WAHA webhook configuration skipped: {e}")

    # Launch WAHA supervisor in background to recover after WAHA restarts
    app.state.waha_supervisor_task = asyncio.create_task(_waha_supervisor(app, 30))

    yield
    # Shutdown
    logger.info("Closing database connections...")
    close_database_connection()
    # Stop supervisor background task
    task: Optional[asyncio.Task] = getattr(app.state, "waha_supervisor_task", None)
    if task:
        task.cancel()
        try:
            await task
        except Exception:
            pass
    logger.info("Closing WAHA client...")
    await close_waha_client()
    logger.info("API successfully shutdown")


app = FastAPI(
    title="ARU-LINK WhatsApp API",
    description="API Backend para Aru-Link",
    version="1.0.0",
    lifespan=lifespan,
    # docs_url="/docs" if DEBUG else None,
    # TBD: Deshabilitar docs en producción
    docs_url="/docs",
    redoc_url="/redoc" if DEBUG else None,
    # TBD: Deshabilitar docs en producción
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
    allow_origins=(
        ["*"]
        if DEBUG
        else [
            "https://aru-link.com",
            "https://www.aru-link.com",
            "https://dash.aru-link.com",
        ]
    ),
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

    from .api.envs import HOST

    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=8000,
        log_level="info",
        server_header=False,
        date_header=False,
    )
