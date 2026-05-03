# tests/unit/test_recharge_provider_mock.py
#
# Unit tests para MockRechargeProvider.
# Sin BD, sin red. 100% unitarios.
#
# SEEDS DETERMINISTAS (verificados experimentalmente):
#   SEED_SUCCESS = 0   → primer random = 0.8444  (< 0.85 → success)
#   SEED_FAILED  = 20  → primer random = 0.9056  (0.85–0.95 → failed)
#   SEED_TIMEOUT = 2   → primer random = 0.9560  (> 0.95 → timeout)

import time
import pytest
from unittest.mock import patch

from infrastructure.external.recharge_provider_mock import MockRechargeProvider
from domain.ports.recharge_provider import RechargeProviderPort
from domain.exceptions import RechargeTimeoutError

# ── Constantes ────────────────────────────────────────────────────────────────

PHONE    = "70123456"
OPERATOR = "tigo"
AMOUNT   = 100.0

SEED_SUCCESS = 0
SEED_FAILED  = 20
SEED_TIMEOUT = 2

REQUIRED_KEYS = {"status", "tx_id", "phone", "operator", "amount", "message", "error"}


# ── TestMockProviderInterface ─────────────────────────────────────────────────

class TestMockProviderInterface:

    def test_cumple_protocol(self):
        """El mock satisface el contrato formal RechargeProviderPort."""
        assert isinstance(MockRechargeProvider(), RechargeProviderPort)

    def test_retorna_dict_con_keys_requeridas_en_exito(self):
        provider = MockRechargeProvider(seed=SEED_SUCCESS)
        with patch.object(provider, '_sleep', lambda: None, create=True):
            result = _charge_no_delay(provider)
        assert result["status"] == "success"
        assert REQUIRED_KEYS == set(result.keys()) & REQUIRED_KEYS
        assert result["tx_id"]    is not None
        assert result["phone"]    == PHONE
        assert result["operator"] == OPERATOR
        assert result["amount"]   == AMOUNT
        assert result["error"]    is None

    def test_retorna_dict_con_keys_requeridas_en_fallo(self):
        provider = MockRechargeProvider(seed=SEED_FAILED)
        result = _charge_no_delay(provider)
        assert result["status"] == "failed"
        assert REQUIRED_KEYS == set(result.keys()) & REQUIRED_KEYS
        assert result["tx_id"] is None
        assert result["error"] is not None


# ── TestMockProviderDeterminism ───────────────────────────────────────────────

class TestMockProviderDeterminism:

    def test_mismo_seed_misma_secuencia_de_status(self):
        """Dos instancias con el mismo seed producen idéntica secuencia de status."""
        p1 = MockRechargeProvider(seed=99)
        p2 = MockRechargeProvider(seed=99)

        statuses_p1, statuses_p2 = [], []
        for _ in range(10):
            statuses_p1.append(_get_status(p1))
            statuses_p2.append(_get_status(p2))

        assert statuses_p1 == statuses_p2

    def test_diferente_seed_produce_distinta_secuencia(self):
        """Seeds distintos muy probablemente generan al menos un status diferente."""
        p1 = MockRechargeProvider(seed=1)
        p2 = MockRechargeProvider(seed=999)

        seq1 = [_get_status(p1) for _ in range(10)]
        seq2 = [_get_status(p2) for _ in range(10)]

        assert seq1 != seq2, "Con seeds tan distintos, las secuencias deben diferir"


# ── TestMockProviderDistribution ─────────────────────────────────────────────

class TestMockProviderDistribution:

    def test_distribucion_aproximada(self):
        """
        1000 llamadas con seed fijo. Sin delay (parcheamos random directamente).
        success >= 800, failed >= 80, timeout >= 30.
        Tolerancia ±20% — es probabilístico.
        """
        provider = MockRechargeProvider(seed=42)
        success, failed, timeout = 0, 0, 0

        for _ in range(1000):
            r = provider._rng.random()
            if r < provider._SUCCESS_THRESHOLD:
                success += 1
            elif r < provider._TIMEOUT_THRESHOLD:
                failed += 1
            else:
                timeout += 1

        assert success >= 800, f"success muy bajo: {success}"
        assert failed  >= 80,  f"failed muy bajo: {failed}"
        assert timeout >= 30,  f"timeout muy bajo: {timeout}"


# ── TestMockProviderTimeout ───────────────────────────────────────────────────

class TestMockProviderTimeout:

    def test_lanza_recharge_timeout_error(self):
        """Forzar roll > _TIMEOUT_THRESHOLD → debe lanzar RechargeTimeoutError."""
        provider = MockRechargeProvider(seed=42)
        with patch.object(provider._rng, 'random', return_value=0.96):
            with pytest.raises(RechargeTimeoutError):
                _charge_no_delay(provider)

    def test_timeout_error_tiene_mensaje_por_defecto(self):
        err = RechargeTimeoutError()
        assert "agotado" in str(err).lower()


# ── TestMockProviderDelay ─────────────────────────────────────────────────────

class TestMockProviderDelay:

    @pytest.mark.slow
    def test_tiene_delay_artificial(self):
        """
        El delay artificial >= DELAY_SECONDS debe ser observable.
        Marcado @slow porque tarda 0.5s.
        """
        provider = MockRechargeProvider(seed=SEED_SUCCESS)
        t0 = time.monotonic()
        provider.charge(PHONE, OPERATOR, AMOUNT)   # llamada real sin parchear sleep
        elapsed = time.monotonic() - t0
        assert elapsed >= MockRechargeProvider.DELAY_SECONDS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _charge_no_delay(provider: MockRechargeProvider) -> dict:
    """Llama charge() parcheando time.sleep para no esperar 0.5s en cada test."""
    with patch("infrastructure.external.recharge_provider_mock.time.sleep"):
        return provider.charge(PHONE, OPERATOR, AMOUNT)


def _get_status(provider: MockRechargeProvider) -> str:
    """Extrae solo el status sin delay y sin lanzar excepción."""
    try:
        return _charge_no_delay(provider)["status"]
    except RechargeTimeoutError:
        return "timeout"
