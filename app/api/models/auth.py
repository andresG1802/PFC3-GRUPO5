"""
Modelos Pydantic para el router de Autenticación
"""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Modelo para solicitud de login"""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Modelo para respuesta de token"""

    access_token: str
    token_type: str
    expires_in: int
    asesor_id: int


class AsesorInfo(BaseModel):
    """Modelo para información del asesor autenticado"""

    id: int
    email: str
    full_name: str
    is_active: bool


class ChangePasswordRequest(BaseModel):
    """Modelo para cambio de contraseña"""

    current_password: str
    new_password: str
