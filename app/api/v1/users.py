"""
Usuarios - Endpoints para gestión de usuarios
"""

from fastapi import APIRouter, HTTPException, Query, Path
from typing import List
from datetime import datetime

# Importar modelos desde el módulo centralizado
from ..models.users import UserBase, UserCreate, UserUpdate, UserResponse

# Configurar router con tags a nivel de clase
router = APIRouter(tags=["Usuarios"])

# Simulación de base de datos en memoria
fake_users_db = [
    {
        "id": 1,
        "email": "admin@example.com",
        "full_name": "Administrador",
        "is_active": True,
        "created_at": datetime.now(),
        "updated_at": None,
    },
    {
        "id": 2,
        "email": "user@example.com",
        "full_name": "Usuario Demo",
        "is_active": True,
        "created_at": datetime.now(),
        "updated_at": None,
    },
]


@router.get("/", response_model=List[UserResponse])
async def get_users(
    skip: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(
        10, ge=1, le=100, description="Número máximo de registros a retornar"
    ),
):
    """
    Obtiene lista de usuarios con paginación

    Args:
        skip: Número de registros a omitir
        limit: Número máximo de registros a retornar

    Returns:
        List[UserResponse]: Lista de usuarios
    """
    return fake_users_db[skip : skip + limit]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int = Path(..., gt=0, description="ID del usuario")):
    """
    Obtiene un usuario específico por ID

    Args:
        user_id: ID del usuario

    Returns:
        UserResponse: Datos del usuario

    Raises:
        HTTPException: Si el usuario no existe
    """
    user = next((user for user in fake_users_db if user["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(user: UserCreate):
    """
    Crea un nuevo usuario

    Args:
        user: Datos del usuario a crear

    Returns:
        UserResponse: Usuario creado

    Raises:
        HTTPException: Si el email ya existe
    """
    # Verificar si el email ya existe
    if any(existing_user["email"] == user.email for existing_user in fake_users_db):
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    # Crear nuevo usuario
    new_user = {
        "id": len(fake_users_db) + 1,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "created_at": datetime.now(),
        "updated_at": None,
    }

    fake_users_db.append(new_user)
    return new_user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int = Path(..., gt=0, description="ID del usuario"),
    user_update: UserUpdate = None,
):
    """
    Actualiza un usuario existente

    Args:
        user_id: ID del usuario
        user_update: Datos a actualizar

    Returns:
        UserResponse: Usuario actualizado

    Raises:
        HTTPException: Si el usuario no existe
    """
    user_index = next(
        (i for i, user in enumerate(fake_users_db) if user["id"] == user_id), None
    )
    if user_index is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user = fake_users_db[user_index]

    # Actualizar campos si se proporcionan
    if user_update.email is not None:
        user["email"] = user_update.email
    if user_update.full_name is not None:
        user["full_name"] = user_update.full_name
    if user_update.is_active is not None:
        user["is_active"] = user_update.is_active

    user["updated_at"] = datetime.now()

    return user


@router.delete("/{user_id}")
async def delete_user(user_id: int = Path(..., gt=0, description="ID del usuario")):
    """
    Elimina un usuario

    Args:
        user_id: ID del usuario

    Returns:
        dict: Mensaje de confirmación

    Raises:
        HTTPException: Si el usuario no existe
    """
    user_index = next(
        (i for i, user in enumerate(fake_users_db) if user["id"] == user_id), None
    )
    if user_index is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    deleted_user = fake_users_db.pop(user_index)
    return {"message": f"Usuario {deleted_user['full_name']} eliminado correctamente"}
