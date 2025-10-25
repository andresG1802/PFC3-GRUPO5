"""
Modelos Pydantic para el router de Usuarios
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    """Modelo base para usuario"""

    email: EmailStr
    full_name: str
    is_active: bool = True


class UserCreate(UserBase):
    """Modelo para crear usuario"""

    password: str


class UserUpdate(BaseModel):
    """Modelo para actualizar usuario"""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Modelo de respuesta para usuario"""

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
