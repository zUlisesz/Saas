# tests/unit/test_config_security.py
#
# Verifica que las credenciales de Supabase no están hardcodeadas en el
# código fuente y que .env.example documenta todas las keys requeridas.
#
# Tests: 3

import pathlib

ROOT = pathlib.Path(__file__).parent.parent.parent


class TestNoHardcodedCredentials:

    def test_supabase_client_no_contiene_url_real(self):
        content = (ROOT / "config" / "supabase_client.py").read_text()
        assert "supabase.co" not in content, \
            "FALLO: La URL de Supabase está hardcodeada en config/supabase_client.py"

    def test_supabase_client_no_contiene_jwt(self):
        content = (ROOT / "config" / "supabase_client.py").read_text()
        assert "eyJhbGci" not in content, \
            "FALLO: La API key JWT está hardcodeada en config/supabase_client.py"


class TestEnvExample:

    def test_env_example_existe_y_tiene_keys_requeridas(self):
        content = (ROOT / ".env.example").read_text()
        assert "SUPABASE_URL" in content
        assert "SUPABASE_KEY" in content
        assert "NEXAPOS_ENV" in content
