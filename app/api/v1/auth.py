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
from ..models.auth import LoginRequest, TokenResponse, AsesorInfo, ChangePasswordRequest

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
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return email
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(email: str = Depends(verify_token)):
    """Obtiene el asesor actual basado en el token"""
    asesor = AsesorModel.find_by_email(email)
    if asesor is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Asesor no encontrado"
        )
    return asesor


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
        data={"sub": asesor["email"]}, expires_delta=access_token_expires
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=JWT_EXPIRE_MINUTES * 60,
        asesor_id=asesor["_id"],
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
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": current_user["email"], "asesor_id": str(current_user["_id"])},
        expires_delta=access_token_expires,
    )

    return {"access_token": access_token, "token_type": "bearer"}
