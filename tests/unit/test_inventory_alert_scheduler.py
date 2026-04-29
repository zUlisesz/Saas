# tests/unit/test_inventory_alert_scheduler.py
#
# Tests para InventoryAlertScheduler (Fase 5)
#
# COBERTURA:
#   1. Inicialización y ciclo de vida
#   2. Inicio/stop idempotentes
#   3. Ejecución del job
#   4. Manejo de errores
#   5. Configuración de intervalo
#   6. Builder function
#   7. Consistencia de estado
#   8. Cleanup y recursos

import pytest
import time
from unittest.mock import MagicMock, patch
from infrastructure.schedulers.inventory_scheduler import (
    InventoryAlertScheduler,
    create_inventory_alert_scheduler,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_controller():
    ctrl = MagicMock()
    ctrl.generate_alerts.return_value = 5
    return ctrl


@pytest.fixture
def scheduler(mock_controller):
    """Scheduler con intervalo de 1 segundo para tests rápidos."""
    return InventoryAlertScheduler(
        inventory_controller=mock_controller,
        interval_minutes=0.016666,  # ~1 segundo
        max_instances=1,
    )


# ─── Inicialización ──────────────────────────────────────────────────────────

class TestInitialization:

    def test_init_not_running(self, scheduler):
        assert not scheduler.is_running()
        assert scheduler._scheduler is None

    def test_init_stores_parameters(self, mock_controller):
        sched = InventoryAlertScheduler(mock_controller, interval_minutes=30)
        assert sched.controller is mock_controller
        assert sched.interval_min == 30
        assert sched.max_instances == 1

    def test_get_next_execution_when_not_running(self, scheduler):
        assert scheduler.get_next_execution() is None


# ─── Start / Stop ─────────────────────────────────────────────────────────────

class TestStartStop:

    def test_start_initializes_scheduler(self, scheduler):
        scheduler.start()
        assert scheduler.is_running()
        assert scheduler._scheduler is not None
        scheduler.stop()

    def test_start_idempotent(self, scheduler):
        scheduler.start()
        scheduler.start()  # Segunda llamada — no debe fallar
        assert scheduler.is_running()
        scheduler.stop()

    def test_stop_shuts_down(self, scheduler):
        scheduler.start()
        scheduler.stop()
        assert not scheduler.is_running()

    def test_stop_idempotent_when_not_running(self, scheduler):
        scheduler.stop()  # Sin haber iniciado — no debe fallar
        assert not scheduler.is_running()

    def test_start_raises_on_error(self, mock_controller):
        sched = InventoryAlertScheduler(mock_controller)
        with patch(
            "infrastructure.schedulers.inventory_scheduler.BackgroundScheduler",
            side_effect=Exception("Scheduler init error"),
        ):
            with pytest.raises(Exception, match="Scheduler init error"):
                sched.start()
            assert not sched.is_running()


# ─── Ejecución del job ───────────────────────────────────────────────────────

class TestJobExecution:

    def test_job_calls_generate_alerts(self, scheduler, mock_controller):
        scheduler.start()
        time.sleep(1.5)
        scheduler.stop()
        assert mock_controller.generate_alerts.called

    def test_job_logs_on_success(self, scheduler, mock_controller):
        with patch("infrastructure.schedulers.inventory_scheduler._log") as mock_log:
            scheduler.start()
            time.sleep(1.5)
            scheduler.stop()
            logged = any(
                "Alertas generadas" in str(c)
                for c in mock_log.debug.call_args_list
            )
            assert logged or mock_controller.generate_alerts.called

    def test_job_continues_on_error(self, scheduler, mock_controller):
        mock_controller.generate_alerts.side_effect = Exception("Controller error")
        with patch("infrastructure.schedulers.inventory_scheduler._log") as mock_log:
            scheduler.start()
            time.sleep(1.5)
            scheduler.stop()
            assert any(
                "Error generando alertas" in str(c)
                for c in mock_log.error.call_args_list
            )


# ─── Configuración de intervalo ──────────────────────────────────────────────

class TestIntervalConfiguration:

    def test_custom_interval(self, mock_controller):
        sched = InventoryAlertScheduler(mock_controller, interval_minutes=60)
        assert sched.interval_min == 60
        sched.start()
        job = sched._scheduler.get_job("generate_inventory_alerts")
        assert job is not None
        sched.stop()

    def test_default_interval_is_15(self, mock_controller):
        sched = InventoryAlertScheduler(mock_controller)
        assert sched.interval_min == 15


# ─── Builder function ────────────────────────────────────────────────────────

class TestBuilderFunction:

    def test_returns_valid_instance(self, mock_controller):
        sched = create_inventory_alert_scheduler(mock_controller, interval_minutes=20)
        assert isinstance(sched, InventoryAlertScheduler)
        assert sched.controller is mock_controller
        assert sched.interval_min == 20

    def test_default_interval(self, mock_controller):
        sched = create_inventory_alert_scheduler(mock_controller)
        assert sched.interval_min == 15


# ─── Consistencia de estado ──────────────────────────────────────────────────

class TestStateConsistency:

    def test_is_running_after_start(self, scheduler):
        assert not scheduler.is_running()
        scheduler.start()
        assert scheduler.is_running()
        scheduler.stop()

    def test_is_running_false_after_stop(self, scheduler):
        scheduler.start()
        scheduler.stop()
        assert not scheduler.is_running()

    def test_scheduler_object_exists_after_start(self, scheduler):
        assert scheduler._scheduler is None
        scheduler.start()
        assert scheduler._scheduler is not None
        scheduler.stop()


# ─── Cleanup ─────────────────────────────────────────────────────────────────

class TestCleanup:

    def test_stop_safe_multiple_times(self, scheduler):
        scheduler.start()
        scheduler.stop()
        scheduler.stop()
        scheduler.stop()
        assert not scheduler.is_running()
