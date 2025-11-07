"""
Pydantic models for the Authentication router
"""

from pydantic import BaseModel, EmailStr, field_validator


class LoginRequest(BaseModel):
    """Modelo para solicitud de login"""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Modelo para respuesta de token"""

    access_token: str
    token_type: str
    expires_in: int
    asesor_id: str


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


class RegisterAsesorRequest(BaseModel):
    """Request model for new advisor registration"""

    email: EmailStr
    password: str
    full_name: str
    role: str = "asesor"  # Por defecto "asesor", puede ser "admin"

    @field_validator("password")
    def validate_password(cls, v: str) -> str:
        """Validate password: non-empty, min 8 chars, at least one special char."""
        if v is None:
            raise ValueError("La contraseña es obligatoria")
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        if not any(not c.isalnum() for c in v):
            raise ValueError(
                "La contraseña debe incluir al menos un carácter especial"
            )
        return v


class RegisterAsesorResponse(BaseModel):
    """Modelo para respuesta de registro de asesor"""

    message: str
    asesor_id: str
    email: str
    full_name: str
    role: str
