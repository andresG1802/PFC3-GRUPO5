from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1.auth import router as auth_router
from .api.v1.health import router as health_router
from .api.v1.interactions import router as interactions_router
from .api.v1.chats import router as chats_router
from .database.connection import get_database, close_database_connection
from .database.seeder import seed_database
from .services.waha_client import close_waha_client
from .utils.logging_config import init_logging
from .middleware import ErrorHandlerMiddleware, TimeoutMiddleware, RateLimitMiddleware


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
    description="""
    ## API Backend para gestión de chats de WhatsApp
    
    Esta API proporciona endpoints para interactuar con chats de WhatsApp a través de WAHA (WhatsApp HTTP API).
    
    ### Características principales:
    - 🚀 **Alto rendimiento** con sistema de caché inteligente
    - 🔒 **Seguridad robusta** con autenticación por API Key
    - 📊 **Logging completo** para monitoreo y debugging
    - ⚡ **Manejo de errores** robusto con reintentos automáticos
    - 📱 **Gestión completa de chats** individuales y grupales
    - 🔄 **Rate limiting** para protección contra abuso
    
    ### Endpoints disponibles:
    - **Chats**: Gestión completa de conversaciones
    - **Auth**: Autenticación y autorización
    - **Health**: Monitoreo del estado del sistema
    - **Interactions**: Gestión de interacciones del bot
    
    ### Tecnologías:
    - FastAPI + Python 3.9+
    - MongoDB para persistencia
    - WAHA para integración con WhatsApp
    - Sistema de caché en memoria
    - Logging estructurado con JSON
    """,
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

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Agregar middlewares de manejo de errores y timeouts
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(TimeoutMiddleware, timeout_seconds=30.0)
app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

app.include_router(auth_router, prefix="/auth")
app.include_router(health_router, prefix="/health")
app.include_router(interactions_router, prefix="/interactions")
app.include_router(chats_router, prefix="/api/chats")

if __name__ == "__main__":
    import uvicorn
    from .api.envs import DEBUG, HOST, PORT

    if DEBUG:
        uvicorn.run(
            "app.main:app", host=HOST, port=PORT, reload=DEBUG, log_level="info"
        )
    else:
        uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="info")
