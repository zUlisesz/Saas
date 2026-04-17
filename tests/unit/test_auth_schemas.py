import pytest
from domain.schemas.auth_schemas import LoginRequest, RegisterRequest
from domain.exceptions import ValidationError


class TestLoginRequest:
    def test_valid(self):
        req = LoginRequest(email="a@b.com", password="secret")
        req.validate()

    def test_empty_email_raises(self):
        with pytest.raises(ValidationError) as exc:
            LoginRequest(email="", password="x").validate()
        assert exc.value.field == "email"

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError) as exc:
            LoginRequest(email="noatsign", password="x").validate()
        assert exc.value.field == "email"

    def test_empty_password_raises(self):
        with pytest.raises(ValidationError) as exc:
            LoginRequest(email="a@b.com", password="").validate()
        assert exc.value.field == "password"

    def test_whitespace_email_raises(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="   ", password="x").validate()


class TestRegisterRequest:
    def test_valid(self):
        RegisterRequest(email="user@example.com", password="123456").validate()

    def test_short_password_raises(self):
        with pytest.raises(ValidationError) as exc:
            RegisterRequest(email="a@b.com", password="123").validate()
        assert exc.value.field == "password"

    def test_no_tld_raises(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b", password="123456").validate()

    def test_missing_domain_raises(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@", password="123456").validate()
