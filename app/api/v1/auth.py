"""
Autenticación - Endpoints para login, logout y gestión de tokens
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from ..envs import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_MINUTES
from datetime import datetime, timedelta
import jwt

# Importar modelos desde el módulo centralizado
from ..models.auth import LoginRequest, TokenResponse, UserInfo, ChangePasswordRequest

# Configurar router con tags a nivel de clase
router = APIRouter(tags=["Autenticación"])
security = HTTPBearer()

# Simulación de usuarios para autenticación
fake_users = {
    "admin@example.com": {
        "id": 1,
        "email": "admin@example.com",
        "full_name": "Administrador",
        "password": "admin123",  # En producción usar hash
        "is_active": True,
    },
    "user@example.com": {
        "id": 2,
        "email": "user@example.com",
        "full_name": "Usuario Demo",
        "password": "user123",  # En producción usar hash
        "is_active": True,
    },
}


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crea un token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

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
    """Obtiene el usuario actual basado en el token"""
    user = fake_users.get(email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado"
        )
    return user


@router.post("/login", response_model=TokenResponse)
async def login(login_data: LoginRequest):
    """
    Autentica un usuario y retorna un token de acceso

    Args:
        login_data: Credenciales de login

    Returns:
        TokenResponse: Token de acceso y información relacionada

    Raises:
        HTTPException: Si las credenciales son inválidas
    """
    user = fake_users.get(login_data.email)

    if not user or user["password"] != login_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Usuario inactivo"
        )

    access_token_expires = timedelta(minutes=JWT_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=JWT_EXPIRE_MINUTES * 60,
        user_id=user["id"],
    )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Cierra la sesión del usuario actual

    Args:
        current_user: Usuario autenticado

    Returns:
        dict: Mensaje de confirmación
    """
    return {"message": "Sesión cerrada correctamente"}


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Obtiene información del usuario autenticado

    Args:
        current_user: Usuario autenticado

    Returns:
        UserInfo: Información del usuario
    """
    return UserInfo(
        id=current_user["id"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        is_active=current_user["is_active"],
    )


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest, current_user: dict = Depends(get_current_user)
):
    """
    Cambia la contraseña del usuario autenticado

    Args:
        password_data: Datos para cambio de contraseña
        current_user: Usuario autenticado

    Returns:
        dict: Mensaje de confirmación

    Raises:
        HTTPException: Si la contraseña actual es incorrecta
    """
    if current_user["password"] != password_data.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contraseña actual incorrecta",
        )

    # En producción, aquí se actualizaría la contraseña en la base de datos
    fake_users[current_user["email"]]["password"] = password_data.new_password

    return {"message": "Contraseña actualizada correctamente"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """
    Renueva el token de acceso del usuario autenticado

    Args:
        current_user: Usuario autenticado

    Returns:
        TokenResponse: Nuevo token de acceso
    """
    access_token_expires = timedelta(minutes=JWT_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": current_user["email"]}, expires_delta=access_token_expires
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=JWT_EXPIRE_MINUTES * 60,
        user_id=current_user["id"],
    )
