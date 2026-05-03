# tests/integration/test_recharge_flow.py
#
# Tests de integración — Fase 6: Recargas Electrónicas.
#
# REQUIEREN: BD de test aislada (Supabase branch o variables en .env.test).
# EXCLUIR del run normal: pytest -m "not integration"
# EJECUTAR con BD:        pytest -m integration
#
# TODO: configurar fixtures test_tenant, test_user y supabase_client
#       en conftest.py cuando haya un entorno de test dedicado.

import pytest


@pytest.mark.integration
class TestRechargeFlowIntegration:

    def test_create_recharge_persiste_en_bd(self):
        """
        Llamar RPC create_recharge directamente.
        Verificar que el registro existe con status='pending'.
        """
        pytest.skip("Requiere BD de test — configurar conftest.py primero")

    def test_complete_recharge_actualiza_status_success(self):
        """
        Dado un recharge en status='pending',
        llamar RPC complete_recharge con status='success'.
        Verificar status='success' y completed_at IS NOT NULL.
        """
        pytest.skip("Requiere BD de test")

    def test_get_history_retorna_datos_con_cajero(self):
        """
        Llamar RPC get_recharge_history.
        Verificar que cajero_name no es None (JOIN con auth.users funciona).
        """
        pytest.skip("Requiere BD de test")

    def test_process_end_to_end_con_mock_provider(self):
        """
        Instanciar RechargeService con MockRechargeProvider(seed=0).
        seed=0 garantiza success en el primer call (roll ≈ 0.8444 < 0.85).
        Llamar service.process(phone, operator, amount).
        Verificar en BD: un recharge con status='success' y ext_tx_id no nulo.
        """
        pytest.skip("Requiere BD de test")

    def test_process_timeout_deja_status_timeout_en_bd(self):
        """
        MockRechargeProvider con _rng.random parcheado a 0.96 (> 0.95).
        Verificar que el recharge tiene status='timeout' en BD
        (no queda 'pending').
        """
        pytest.skip("Requiere BD de test")

    def test_external_tx_id_unique_constraint(self):
        """
        Insertar dos recharges con el mismo external_tx_id.
        El segundo debe fallar por UNIQUE constraint en BD.
        """
        pytest.skip("Requiere BD de test")
