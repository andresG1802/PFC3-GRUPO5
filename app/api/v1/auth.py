"""
Autenticación - Endpoints para login, logout y gestión de tokens de asesores
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from ..envs import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_MINUTES
from datetime import datetime, timedelta
import jwt
import hashlib

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

# Configurar router con tags a nivel de clase
router = APIRouter(tags=["Autenticación"])
security = HTTPBearer()


# Función para hashear contraseñas (mejorada)
def hash_password(password: str) -> str:
    """Hashea una contraseña usando SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crea un token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)

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
        TokenResponse: Token de acceso y información relacionada

    Raises:
        HTTPException: Si las credenciales son inválidas
    """
    asesor = AsesorModel.find_by_email(login_data.email)

    if not asesor or asesor["password"] != hash_password(login_data.password):
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

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=JWT_EXPIRE_MINUTES * 60,
        asesor_id=current_user["_id"],
    )


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
    if current_user["password"] != hash_password(password_data.current_password):
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

    return {"access_token": access_token, "token_type": "bearer"}
