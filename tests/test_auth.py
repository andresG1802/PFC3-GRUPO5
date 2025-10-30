"""
Tests para endpoints de autenticación
"""

from fastapi.testclient import TestClient
from unittest.mock import patch
from datetime import timedelta

from app.api.v1.auth import hash_password, create_access_token


class TestLogin:
    """Tests para el endpoint de login"""
    
    def test_login_success(self, client: TestClient, mock_asesor_model):
        """Test de login exitoso"""
        response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "password"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert "asesor_id" in data
        assert "expires_in" in data
        assert "asesor_id" in data
    
    def test_login_invalid_email(self, client: TestClient, mock_asesor_model):
        """Test de login con email inválido"""
        response = client.post(
            "/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "password"
            }
        )
        
        assert response.status_code == 401
        assert "Credenciales incorrectas" in response.json()["detail"]
    
    def test_login_invalid_password(self, client: TestClient, mock_asesor_model):
        """Test de login con contraseña incorrecta"""
        response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "wrong_password"
            }
        )
        
        assert response.status_code == 401
        assert "Credenciales incorrectas" in response.json()["detail"]
    
    def test_login_inactive_user(self, client: TestClient):
        """Test de login con usuario inactivo"""
        # Configurar usuario inactivo usando patch
        inactive_user = {
            "_id": "507f1f77bcf86cd799439011",
            "email": "inactive@example.com",
            "password": hash_password("password"),
            "full_name": "Inactive User",
            "role": "asesor",
            "is_active": False
        }
        
        with patch('app.database.models.AsesorModel.find_by_email', return_value=inactive_user):
            response = client.post(
                "/auth/login",
                json={
                    "email": "inactive@example.com",
                    "password": "password"
                }
            )
        
        assert response.status_code == 401
        assert "Credenciales incorrectas" in response.json()["detail"]
    
    def test_login_invalid_email_format(self, client: TestClient):
        """Test de login con formato de email inválido"""
        response = client.post(
            "/auth/login",
            json={
                "email": "invalid-email",
                "password": "password"
            }
        )
        
        assert response.status_code == 422  # Validation error


class TestRegister:
    """Tests para el endpoint de registro"""
    
    def test_register_success(self, client: TestClient, mock_asesor_model, admin_auth_headers):
        """Test de registro exitoso"""
        response = client.post(
            "/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "newpassword",
                "full_name": "New User",
                "role": "asesor"
            },
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Asesor registrado exitosamente"
        assert data["email"] == "newuser@example.com"
        assert data["full_name"] == "New User"
        assert data["role"] == "asesor"
        assert "asesor_id" in data
    
    def test_register_existing_email(self, client: TestClient, mock_asesor_model, admin_auth_headers):
        """Test de registro con email existente"""
        response = client.post(
            "/auth/register",
            json={
                "email": "test@example.com",  # Email que ya existe
                "password": "newpassword",
                "full_name": "New User",
                "role": "asesor"
            },
            headers=admin_auth_headers
        )
        
        assert response.status_code == 400
        assert "El email ya está registrado" in response.json()["detail"]
    
    def test_register_invalid_role(self, client: TestClient, mock_asesor_model, admin_auth_headers):
        """Test de registro con rol inválido"""
        response = client.post(
            "/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "newpassword",
                "full_name": "New User",
                "role": "invalid_role"
            },
            headers=admin_auth_headers
        )
        
        assert response.status_code == 400
        assert "Rol inválido" in response.json()["detail"]
    
    def test_register_without_admin_permission(self, client: TestClient, auth_headers):
        """Test de registro sin permisos de administrador"""
        response = client.post(
            "/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "newpassword",
                "full_name": "New User",
                "role": "asesor"
            },
            headers=auth_headers  # Usuario normal, no admin
        )
        
        assert response.status_code == 403
        assert "Acceso denegado" in response.json()["detail"]
    
    def test_register_without_authentication(self, client: TestClient):
        """Test de registro sin autenticación"""
        response = client.post(
            "/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "newpassword",
                "full_name": "New User",
                "role": "asesor"
            }
        )
        
        assert response.status_code == 403


class TestLogout:
    """Tests para el endpoint de logout"""
    
    def test_logout_success(self, client: TestClient, auth_headers):
        """Test de logout exitoso"""
        response = client.post("/auth/logout", headers=auth_headers)
        
        assert response.status_code == 200
        assert "Sesión cerrada correctamente" in response.json()["message"]
    
    def test_logout_without_authentication(self, client: TestClient):
        """Test de logout sin autenticación"""
        response = client.post("/auth/logout")
        
        assert response.status_code == 403


class TestGetAsesorInfo:
    """Tests para el endpoint de información del asesor"""
    
    def test_get_asesor_info_success(self, client: TestClient, auth_headers, mock_asesor_model):
        """Test de obtención de información del asesor exitosa"""
        response = client.get("/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["full_name"] == "Test User"
        assert data["role"] == "asesor"
        assert data["is_active"] is True
        assert "password" not in data  # La contraseña no debe estar en la respuesta
    
    def test_get_asesor_info_without_authentication(self, client: TestClient):
        """Test de obtención de información sin autenticación"""
        response = client.get("/auth/me")
        
        assert response.status_code == 403


class TestChangePassword:
    """Tests para el endpoint de cambio de contraseña"""
    
    def test_change_password_success(self, client: TestClient, auth_headers, mock_asesor_model):
        """Test de cambio de contraseña exitoso"""
        response = client.post(
            "/auth/change-password",
            json={
                "current_password": "password",
                "new_password": "newpassword123"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "Contraseña actualizada exitosamente" in response.json()["message"]
    
    def test_change_password_wrong_current(self, client: TestClient, auth_headers, mock_asesor_model):
        """Test de cambio de contraseña con contraseña actual incorrecta"""
        response = client.post(
            "/auth/change-password",
            json={
                "current_password": "wrong_password",
                "new_password": "newpassword123"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "Contraseña actual incorrecta" in response.json()["detail"]
    
    def test_change_password_without_authentication(self, client: TestClient):
        """Test de cambio de contraseña sin autenticación"""
        response = client.post(
            "/auth/change-password",
            json={
                "current_password": "password",
                "new_password": "newpassword123"
            }
        )
        
        assert response.status_code == 403


class TestRefreshToken:
    """Tests para el endpoint de refresh de token"""
    
    def test_refresh_token_success(self, client: TestClient, auth_headers):
        """Test de refresh de token exitoso"""
        response = client.post("/auth/refresh", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert "asesor_id" in data
    
    def test_refresh_token_without_authentication(self, client: TestClient):
        """Test de refresh de token sin autenticación"""
        response = client.post("/auth/refresh")
        
        assert response.status_code == 403


class TestTokenValidation:
    """Tests para validación de tokens"""
    
    def test_expired_token(self, client: TestClient, mock_asesor_model):
        """Test con token expirado"""
        # Crear token expirado
        expired_token = create_access_token(
            data={"sub": "test@example.com", "role": "asesor"},
            expires_delta=timedelta(seconds=-1)  # Token ya expirado
        )
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/auth/me", headers=headers)
        
        assert response.status_code == 401
        assert "Token expirado" in response.json()["detail"]
    
    def test_invalid_token_format(self, client: TestClient):
        """Test con formato de token inválido"""
        headers = {"Authorization": "Bearer invalid_token_format"}
        response = client.get("/auth/me", headers=headers)
        
        assert response.status_code == 500
        assert "Ha ocurrido un error inesperado" in response.json()["detail"]
    
    def test_missing_authorization_header(self, client: TestClient):
        """Test sin header de autorización"""
        response = client.get("/auth/me")
        
        assert response.status_code == 403


class TestUtilityFunctions:
    """Tests para funciones utilitarias"""
    
    def test_hash_password(self):
        """Test de función de hash de contraseña"""
        password = "test_password"
        hashed = hash_password(password)
        
        assert hashed != password
        assert len(hashed) == 64  # SHA-256 produce hash de 64 caracteres
        assert hash_password(password) == hashed  # Debe ser determinístico
    
    def test_create_access_token(self):
        """Test de creación de token de acceso"""
        data = {"sub": "test@example.com", "role": "asesor"}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verificar que el token contiene los datos correctos
        import jwt
        from app.api.envs import JWT_SECRET_KEY, JWT_ALGORITHM
        
        decoded = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        assert decoded["sub"] == "test@example.com"
        assert decoded["role"] == "asesor"
        assert "exp" in decoded