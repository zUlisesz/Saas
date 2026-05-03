# tests/unit/test_recharge_service.py
#
# Unit tests para RechargeService — Fase 6.
# Sin BD, sin red, sin Session real. 100% unitarios.
#
# PATRÓN: idéntico a test_inventory_service_fase5.py
#   - MagicMock para provider y repo
#   - patch("domain.services.recharge_service.Session")
#   - pytest con clases
#
# Total: 25 tests

import pytest
from unittest.mock import MagicMock, patch

from domain.services.recharge_service import RechargeService
from domain.schemas.recharge_schemas import RechargeResponse
from domain.exceptions import (
    InvalidPhoneError, InvalidOperatorError, InvalidAmountError,
    RechargeTimeoutError, RechargeProviderError,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

TENANT   = "tenant-abc"
USER_ID  = "user-001"
PHONE    = "70123456"
OPERATOR = "tigo"
AMOUNT   = 100.0


def _make_svc(provider=None, repo=None, event_svc=None):
    provider = provider or MagicMock()
    svc = RechargeService(provider=provider, recharge_repo=repo, event_service=event_svc)
    return svc, provider, repo


def _mock_session(tenant=TENANT, user_id=USER_ID):
    """Context manager: parchea Session en el módulo del servicio."""
    _user = type("User", (), {"id": user_id})()
    return patch(
        "domain.services.recharge_service.Session",
        tenant_id=tenant,
        current_user=_user,
    )


def _success_result():
    return {
        "status": "success", "tx_id": "tx-123", "phone": PHONE,
        "operator": OPERATOR, "amount": AMOUNT, "message": "ok", "error": None,
    }


def _failed_result():
    return {
        "status": "failed", "tx_id": None, "phone": PHONE,
        "operator": OPERATOR, "amount": AMOUNT, "message": "fail",
        "error": "Saldo insuficiente", "error_code": None,
    }


# ── TestGetOperators ──────────────────────────────────────────────────────────

class TestGetOperators:

    def test_retorna_todas_las_operadoras(self):
        svc, _, _ = _make_svc()
        ops = svc.get_operators()
        assert len(ops) == 5
        ids = {op["id"] for op in ops}
        assert ids == {"movicel", "comcel", "viva", "entel", "tigo"}

    def test_amounts_son_listas_no_vacias(self):
        svc, _, _ = _make_svc()
        for op in svc.get_operators():
            assert len(op["amounts"]) > 0


# ── TestEstimateCommission ────────────────────────────────────────────────────

class TestEstimateCommission:

    def test_comision_tigo_3_porciento(self):
        svc, _, _ = _make_svc()
        assert svc.estimate_commission("tigo", 100.0) == 3.0

    def test_comision_entel_4_porciento(self):
        svc, _, _ = _make_svc()
        assert svc.estimate_commission("entel", 100.0) == 4.0


# ── TestProcessValidation ─────────────────────────────────────────────────────

class TestProcessValidation:

    def test_phone_invalido_lanza_invalid_phone_error(self):
        svc, _, _ = _make_svc()
        with _mock_session():
            with pytest.raises(InvalidPhoneError):
                svc.process("123", OPERATOR, AMOUNT)

    def test_operator_invalido_lanza_invalid_operator_error(self):
        svc, _, _ = _make_svc()
        with _mock_session():
            with pytest.raises(InvalidOperatorError):
                svc.process(PHONE, "telcel", AMOUNT)

    def test_amount_bajo_minimo_lanza_invalid_amount_error(self):
        svc, _, _ = _make_svc()
        with _mock_session():
            with pytest.raises(InvalidAmountError):
                svc.process(PHONE, OPERATOR, 5.0)

    def test_amount_sobre_maximo_lanza_invalid_amount_error(self):
        svc, _, _ = _make_svc()
        with _mock_session():
            with pytest.raises(InvalidAmountError):
                svc.process(PHONE, OPERATOR, 9999.0)

    def test_sin_sesion_lanza_excepcion(self):
        svc, _, _ = _make_svc()
        with _mock_session(tenant=None):
            with pytest.raises(Exception):
                svc.process(PHONE, OPERATOR, AMOUNT)


# ── TestProcessSuccess ────────────────────────────────────────────────────────

class TestProcessSuccess:

    def _setup(self):
        provider = MagicMock()
        provider.charge.return_value = _success_result()
        repo = MagicMock()
        repo.create.return_value = "recharge-uuid-1"
        svc, _, _ = _make_svc(provider=provider, repo=repo)
        return svc, provider, repo

    def test_llama_a_provider_charge(self):
        svc, provider, _ = self._setup()
        with _mock_session():
            svc.process(PHONE, OPERATOR, AMOUNT)
        provider.charge.assert_called_once_with(PHONE, OPERATOR, AMOUNT)

    def test_llama_a_repo_create_con_pending(self):
        svc, _, repo = self._setup()
        with _mock_session():
            svc.process(PHONE, OPERATOR, AMOUNT)
        repo.create.assert_called_once()
        kwargs = repo.create.call_args.kwargs
        assert kwargs["phone"]    == PHONE
        assert kwargs["operator"] == OPERATOR
        assert kwargs["amount"]   == AMOUNT
        assert kwargs["tenant_id"] == TENANT

    def test_llama_a_repo_update_status_con_success(self):
        svc, _, repo = self._setup()
        with _mock_session():
            svc.process(PHONE, OPERATOR, AMOUNT)
        repo.update_status.assert_called_once()
        kwargs = repo.update_status.call_args.kwargs
        assert kwargs["status"]    == "success"
        assert kwargs["ext_tx_id"] == "tx-123"

    def test_retorna_recharge_response(self):
        svc, _, _ = self._setup()
        with _mock_session():
            result = svc.process(PHONE, OPERATOR, AMOUNT)
        assert isinstance(result, RechargeResponse)
        assert result.status == "success"
        assert result.tx_id  == "tx-123"
        assert result.phone  == PHONE

    def test_emite_evento_recharge_completed(self):
        provider = MagicMock()
        provider.charge.return_value = _success_result()
        event_svc = MagicMock()
        svc, _, _ = _make_svc(provider=provider, event_svc=event_svc)
        with _mock_session():
            svc.process(PHONE, OPERATOR, AMOUNT)
        event_svc.emit.assert_called_once()
        args = event_svc.emit.call_args[0]
        assert args[1] == "recharge_completed"


# ── TestProcessFailure ────────────────────────────────────────────────────────

class TestProcessFailure:

    def _setup(self):
        provider = MagicMock()
        provider.charge.return_value = _failed_result()
        repo = MagicMock()
        repo.create.return_value = "recharge-uuid-2"
        svc, _, _ = _make_svc(provider=provider, repo=repo)
        return svc, provider, repo

    def test_provider_falla_actualiza_status_failed(self):
        svc, _, repo = self._setup()
        with _mock_session():
            svc.process(PHONE, OPERATOR, AMOUNT)
        kwargs = repo.update_status.call_args.kwargs
        assert kwargs["status"] == "failed"

    def test_provider_falla_no_emite_evento(self):
        provider = MagicMock()
        provider.charge.return_value = _failed_result()
        event_svc = MagicMock()
        svc, _, _ = _make_svc(provider=provider, event_svc=event_svc)
        with _mock_session():
            svc.process(PHONE, OPERATOR, AMOUNT)
        event_svc.emit.assert_not_called()

    def test_provider_falla_retorna_response_con_error(self):
        svc, _, _ = self._setup()
        with _mock_session():
            result = svc.process(PHONE, OPERATOR, AMOUNT)
        assert result.status == "failed"
        assert result.error  == "Saldo insuficiente"


# ── TestProcessTimeout ────────────────────────────────────────────────────────

class TestProcessTimeout:

    def _setup_timeout(self):
        provider = MagicMock()
        provider.charge.side_effect = RechargeTimeoutError()
        repo = MagicMock()
        repo.create.return_value = "recharge-uuid-3"
        event_svc = MagicMock()
        svc, _, _ = _make_svc(provider=provider, repo=repo, event_svc=event_svc)
        return svc, provider, repo, event_svc

    def test_timeout_propaga_excepcion(self):
        svc, _, _, _ = self._setup_timeout()
        with _mock_session():
            with pytest.raises(RechargeTimeoutError):
                svc.process(PHONE, OPERATOR, AMOUNT)

    def test_timeout_actualiza_status_en_bd(self):
        svc, _, repo, _ = self._setup_timeout()
        with _mock_session():
            with pytest.raises(RechargeTimeoutError):
                svc.process(PHONE, OPERATOR, AMOUNT)
        repo.update_status.assert_called_once()
        kwargs = repo.update_status.call_args.kwargs
        assert kwargs["status"] == "timeout"

    def test_timeout_no_emite_evento(self):
        svc, _, _, event_svc = self._setup_timeout()
        with _mock_session():
            with pytest.raises(RechargeTimeoutError):
                svc.process(PHONE, OPERATOR, AMOUNT)
        event_svc.emit.assert_not_called()


# ── TestProcessRepoPendingFails ───────────────────────────────────────────────

class TestProcessRepoPendingFails:

    def test_repo_create_falla_proceso_continua(self):
        """BD caída en _create_pending → el provider se llama igual."""
        provider = MagicMock()
        provider.charge.return_value = _success_result()
        repo = MagicMock()
        repo.create.side_effect = Exception("BD down")
        svc, _, _ = _make_svc(provider=provider, repo=repo)

        with _mock_session():
            result = svc.process(PHONE, OPERATOR, AMOUNT)

        provider.charge.assert_called_once()
        # recharge_id=None → _complete() cae en fallback de memoria
        assert isinstance(result, RechargeResponse)

    def test_repo_update_falla_no_lanza_excepcion(self):
        """
        _complete() captura excepciones y hace fallback a memoria.
        No debe propagarse al caller — el cajero ya recibió confirmación
        del proveedor.
        """
        provider = MagicMock()
        provider.charge.return_value = _success_result()
        repo = MagicMock()
        repo.create.return_value = "recharge-uuid-4"
        repo.update_status.side_effect = Exception("BD down al actualizar")
        svc, _, _ = _make_svc(provider=provider, repo=repo)

        with _mock_session():
            result = svc.process(PHONE, OPERATOR, AMOUNT)

        # No lanza — el resultado del provider sí llegó
        assert result.status == "success"
        # El resultado quedó en memoria como fallback
        assert len(svc._memory_history) == 1


# ── TestGetHistory ────────────────────────────────────────────────────────────

class TestGetHistory:

    def test_con_repo_llama_repo_get_history(self):
        repo = MagicMock()
        repo.get_history.return_value = [{"id": "h-1"}]
        svc, _, _ = _make_svc(repo=repo)

        with _mock_session():
            result = svc.get_history()

        repo.get_history.assert_called_once_with(tenant_id=TENANT, limit=50)
        assert result == [{"id": "h-1"}]

    def test_sin_repo_retorna_memory_history(self):
        svc, _, _ = _make_svc()   # sin repo
        svc._memory_history = [{"status": "success", "amount": 100.0}]

        with _mock_session():
            result = svc.get_history()

        assert result == [{"status": "success", "amount": 100.0}]

    def test_sin_sesion_lanza_excepcion(self):
        svc, _, _ = _make_svc()
        with _mock_session(tenant=None):
            with pytest.raises(Exception):
                svc.get_history()
