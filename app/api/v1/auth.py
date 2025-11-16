"""
Autenticación - Endpoints para login, logout y gestión de tokens de asesores
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from ..envs import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_MINUTES
from datetime import datetime, timedelta, timezone
import jwt
import hashlib
import os
import hmac

# Importar modelos desde el módulo centralizado
from ..models.auth import (
    LoginRequest,
    TokenResponse,
    ChangePasswordRequest,
    RegisterAsesorRequest,
    RegisterAsesorResponse,
)

# Importar modelo de asesor de la base de datos
from ...database.models import AsesorModel
from ...database.models import InteractionModel
from ...services.waha_client import get_waha_client
from ...services.cache import get_cache, cache_key_for_overview
from ..models.chats import ChatOverview
import asyncio

# Configurar router con tags a nivel de clase
router = APIRouter(tags=["Autenticación"])
security = HTTPBearer()


# Configuración de hashing de contraseñas
PBKDF2_ITERATIONS = 120000
SALT_BYTES = 12  # Salt de 12 bytes según requisito


def hash_password(password: str) -> str:
    """Genera un hash seguro usando PBKDF2-HMAC-SHA256 con salt de 12 bytes.

    Formato de almacenado: pbkdf2_sha256$<iteraciones>$<salt_hex>$<hash_hex>
    """
    salt = os.urandom(SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifica una contraseña contra un hash almacenado.

    - Soporta formato PBKDF2-HMAC-SHA256 con salt y iteraciones.
    - Mantiene compatibilidad con hashes legacy de SHA-256 plano (64 hex).
    """
    try:
        if stored_hash.startswith("pbkdf2_sha256$"):
            try:
                _, iter_str, salt_hex, hash_hex = stored_hash.split("$")
                iterations = int(iter_str)
                salt = bytes.fromhex(salt_hex)
                expected = bytes.fromhex(hash_hex)
                dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
                return hmac.compare_digest(dk, expected)
            except Exception:
                return False

        # Compatibilidad: SHA-256 plano (no recomendado)
        legacy = hashlib.sha256(password.encode()).hexdigest()
        return hmac.compare_digest(legacy, stored_hash)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crea un token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verifica y decodifica el token JWT"""
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
        )
        email: str = payload.get("sub")
        role: str = payload.get("role", "asesor")  # Extraer rol del token
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {"email": email, "role": role}
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(token_data: dict = Depends(verify_token)):
    """Obtiene el asesor actual desde el token"""
    asesor = AsesorModel.find_by_email(token_data["email"])
    if asesor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asesor no encontrado"
        )
    # Agregar el rol del token al objeto asesor
    asesor["role"] = token_data["role"]
    return asesor


def get_current_admin(current_user: dict = Depends(get_current_user)):
    """Middleware para verificar que el usuario actual es un administrador"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Se requieren permisos de administrador",
        )
    return current_user


@router.post("/login", response_model=TokenResponse)
async def login(login_data: LoginRequest):
    """
    Autentica un asesor y retorna un token de acceso

    Args:
        login_data: Credenciales de login

    Returns:
        TokenResponse: Token de acceso y información del asesor

    Raises:
        HTTPException: Si las credenciales son inválidas
    """
    asesor = AsesorModel.find_by_email(login_data.email)

    if not asesor or not verify_password(
        login_data.password, asesor.get("password", "")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not asesor["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Asesor inactivo"
        )

    access_token_expires = timedelta(minutes=JWT_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": asesor["email"], "role": asesor.get("role", "asesor")},
        expires_delta=access_token_expires,
    )

    # Prewarm chats overview cache asynchronously to improve UX after login
    try:
        asyncio.create_task(_prewarm_overview_cache(limit=10, offset=0))
    except Exception:
        # Never block or fail login due to prewarming issues
        pass

    return TokenResponse(
        access_token=access_token,
        asesor_id=str(asesor.get("_id")),
    )


async def _prewarm_overview_cache(limit: int = 10, offset: int = 0) -> None:
    """Prewarm chats overview cache using WAHA and pending interactions.

    This runs in background, fetching a small overview and storing it in Redis cache
    under the same key scheme used by the chats overview endpoint.
    """
    try:
        # Build ids filter from pending interactions (phone/chat_id)
        ids_filter_set = set()
        interaction_id_map: dict[str, str] = {}
        interactions: list[dict] = []
        try:
            total_interactions = InteractionModel.count_all(state="pending")
            interactions = (
                InteractionModel.find_all(skip=0, limit=total_interactions, state="pending")
                if total_interactions and total_interactions > 0
                else []
            )
            for it in interactions:
                phone = (it.get("phone") or "").strip()
                chat_id = (it.get("chat_id") or "").strip()
                mongo_id = it.get("_id")
                if phone:
                    ids_filter_set.add(phone)
                    if mongo_id:
                        interaction_id_map[phone] = str(mongo_id)
                elif chat_id and "@" in chat_id:
                    ids_filter_set.add(chat_id)
                    if mongo_id:
                        interaction_id_map[chat_id] = str(mongo_id)
        except Exception:
            ids_filter_set = set()

        ids_filter = list(ids_filter_set)

        waha_client = await get_waha_client()
        raw_chats: list[dict] = []
        try:
            raw_chats = await waha_client.get_chats_overview(limit=limit, offset=offset, ids=ids_filter or None)
        except Exception:
            try:
                raw_chats = await waha_client.get_chats(limit=limit, offset=offset)
            except Exception:
                raw_chats = []

        # Normalize into ChatOverview dicts and attach interaction_id when present
        overview_chats: list[dict] = []
        for raw_chat in raw_chats:
            try:
                chat_type = "group" if raw_chat.get("isGroup", False) else "individual"
                overview_data = {
                    "id": raw_chat.get("id", ""),
                    "name": raw_chat.get("name") or raw_chat.get("formattedTitle", "Chat sin nombre"),
                    "type": chat_type,
                    "timestamp": raw_chat.get("timestamp"),
                    "unread_count": raw_chat.get("unreadCount", 0),
                    "archived": raw_chat.get("archived", False),
                    "pinned": raw_chat.get("pinned", False),
                }
                chat_obj = ChatOverview(**overview_data)
                chat_dict = chat_obj.dict()
                interaction_id = interaction_id_map.get(chat_dict.get("id"))
                if interaction_id:
                    chat_dict["interaction_id"] = interaction_id
                overview_chats.append(chat_dict)
            except Exception:
                continue

        # Apply simple pagination slice in case backend ignores params
        try:
            overview_chats = overview_chats[offset : offset + limit]
        except Exception:
            pass

        cache = get_cache()
        cache_key = cache_key_for_overview(limit, offset, ids_filter if ids_filter else None)
        cache.set(cache_key, overview_chats, ttl=300)
    except Exception:
        # Silently ignore errors to avoid affecting login
        pass


@router.post("/register", response_model=RegisterAsesorResponse)
async def register_asesor(
    register_data: RegisterAsesorRequest,
    current_admin: dict = Depends(get_current_admin),
):
    """
    Registra un nuevo asesor (solo administradores)

    Args:
        register_data: Datos del nuevo asesor
        current_admin: Administrador actual (verificado por middleware)

    Returns:
        RegisterAsesorResponse: Información del asesor creado

    Raises:
        HTTPException: Si el email ya existe o hay errores de validación
    """
    # Verificar si el email ya existe
    existing_asesor = AsesorModel.find_by_email(register_data.email)
    if existing_asesor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado",
        )

    # Validar rol
    if register_data.role not in ["asesor", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rol inválido. Debe ser 'asesor' o 'admin'",
        )

    # Hashear contraseña
    hashed_password = hash_password(register_data.password)

    # Crear nuevo asesor
    try:
        asesor_id = AsesorModel.create_asesor(
            email=register_data.email,
            password=hashed_password,
            full_name=register_data.full_name,
            role=register_data.role,
        )

        return RegisterAsesorResponse(
            message="Asesor registrado exitosamente",
            asesor_id=str(asesor_id),
            email=register_data.email,
            full_name=register_data.full_name,
            role=register_data.role,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear asesor: {str(e)}",
        )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Cierra la sesión del asesor actual

    Args:
        current_user: Asesor autenticado

    Returns:
        dict: Mensaje de confirmación
    """
    return {"message": "Sesión cerrada correctamente"}


@router.get("/me")
async def get_asesor_info(current_user: dict = Depends(get_current_user)):
    """
    Obtiene la información del asesor actual

    Args:
        current_user: Asesor actual obtenido del token

    Returns:
        dict: Información del asesor (sin contraseña)
    """
    # Remover información sensible
    asesor_info = current_user.copy()
    asesor_info.pop("password", None)

    # Convertir ObjectId a string para serialización JSON
    if "_id" in asesor_info:
        asesor_info["_id"] = str(asesor_info["_id"])

    return asesor_info


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest, current_user: dict = Depends(get_current_user)
):
    """
    Cambia la contraseña del asesor actual

    Args:
        password_data: Datos con contraseña actual y nueva
        current_user: Asesor actual obtenido del token

    Returns:
        dict: Mensaje de confirmación

    Raises:
        HTTPException: Si la contraseña actual es incorrecta
    """
    # Verificar contraseña actual
    if not verify_password(
        password_data.current_password, current_user.get("password", "")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contraseña actual incorrecta",
        )

    # Actualizar contraseña en la base de datos
    hashed_new_password = hash_password(password_data.new_password)
    AsesorModel.update_by_email(
        current_user["email"], {"password": hashed_new_password}
    )

    return {"message": "Contraseña actualizada exitosamente"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """
    Refresca el token de acceso del asesor

    Args:
        current_user: Asesor actual obtenido del token

    Returns:
        TokenResponse: Nuevo token de acceso
    """
    # Crear nuevo token de acceso
    access_token_expires = timedelta(minutes=JWT_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": current_user["email"], "role": current_user.get("role", "asesor")},
        expires_delta=access_token_expires,
    )

    return TokenResponse(
        access_token=access_token,
        asesor_id=str(current_user["_id"]),
    )
