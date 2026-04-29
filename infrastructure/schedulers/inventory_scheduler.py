# infrastructure/schedulers/inventory_scheduler.py
#
# NUEVA — Fase 5 (29 Abril 2026)
#
# JUSTIFICACIÓN:
#   Las alertas de inventario necesitan generarse periódicamente para que
#   los usuarios vean cambios sin actualizar la página manualmente.
#
#   DECISIÓN: APScheduler en lugar de Celery porque:
#     • Más liviano para aplicaciones monolíticas (NexaPOS es una sola app)
#     • No requiere Redis/RabbitMQ — solo se ejecuta en el proceso de la app
#     • Perfecto para pequeña/mediana escala (hasta 1000s de productos)
#     • Si escala a Fase 7+, se cambia a Celery sin cambios en la lógica
#
# INTEGRACIÓN:
#   1. Se instancia en ServiceContainer y se expone como singleton
#   2. Se inicia en App._init_dependencies() tras inicializar dependencias
#   3. APScheduler detiene el thread automáticamente cuando el proceso termina
#
# PATRÓN:
#   • Stateless: no mantiene estado de la app
#   • Solo orquesta: llama controller.generate_alerts() cada X minutos
#   • Fire & forget: si una ejecución falla, la siguiente se intenta igual
#   • Logging: registra éxitos y errores para debugging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

_log = logging.getLogger(__name__)


class InventoryAlertScheduler:
    """
    Job scheduler para generar alertas de inventario periódicamente.

    CICLO DE VIDA:
        1. __init__()      — Configura el scheduler pero NO lo inicia
        2. start()         — Inicia el scheduler en background
        3. stop()          — Detiene el scheduler gracefully
        4. is_running()    — Verifica si está activo
        5. get_next_execution() — Timestamp de la próxima ejecución
    """

    def __init__(
        self,
        inventory_controller,
        interval_minutes: int = 15,
        max_instances: int = 1,
    ):
        """
        Args:
            inventory_controller: InventoryController con método generate_alerts()
            interval_minutes:     Intervalo en minutos (default 15)
            max_instances:        Max instancias concurrentes del job (siempre 1
                                  para evitar race conditions en la RPC de BD)
        """
        self.controller    = inventory_controller
        self.interval_min  = interval_minutes
        self.max_instances = max_instances
        self._scheduler: BackgroundScheduler | None = None
        self._is_running   = False

    # ─────────────────────────────────────────────────────────────────────

    def start(self) -> None:
        """
        Inicia el scheduler en background.
        Idempotente — si ya está corriendo, no hace nada.
        """
        if self._is_running:
            _log.info("InventoryAlertScheduler ya está corriendo, ignorando start()")
            return

        try:
            self._scheduler = BackgroundScheduler()
            self._scheduler.add_job(
                func=self._generate_alerts_job,
                trigger=IntervalTrigger(minutes=self.interval_min),
                id="generate_inventory_alerts",
                name="Generate Inventory Alerts",
                max_instances=self.max_instances,
                replace_existing=True,
                misfire_grace_time=30,
            )
            self._scheduler.start()
            self._is_running = True
            _log.info(
                f"InventoryAlertScheduler iniciado | Intervalo: {self.interval_min} min"
            )
        except Exception as e:
            _log.error(f"Error al iniciar InventoryAlertScheduler: {e}", exc_info=True)
            self._is_running = False
            raise

    def stop(self) -> None:
        """
        Detiene el scheduler gracefully.
        Idempotente — si no está corriendo, no hace nada.
        """
        if not self._is_running or self._scheduler is None:
            return

        try:
            self._scheduler.shutdown(wait=True)
            self._is_running = False
            _log.info("InventoryAlertScheduler detenido")
        except Exception as e:
            _log.error(f"Error al detener InventoryAlertScheduler: {e}", exc_info=True)

    def is_running(self) -> bool:
        """Retorna True si el scheduler está activo."""
        return self._is_running

    def get_next_execution(self) -> str | None:
        """
        Retorna timestamp de la próxima ejecución, o None si no está corriendo.
        Útil para UI (mostrar "próxima actualización en X minutos").
        """
        if not self._scheduler:
            return None
        job = self._scheduler.get_job("generate_inventory_alerts")
        if job:
            return str(job.next_run_time)
        return None

    # ─── Private: Job handler ─────────────────────────────────────────────

    def _generate_alerts_job(self) -> None:
        """
        Cuerpo del job que se ejecuta periódicamente.
        Fire & forget — nunca relanza excepciones para no interrumpir el scheduler.
        """
        try:
            count = self.controller.generate_alerts()
            _log.debug(f"Alertas generadas: {count} nuevas")
        except Exception as e:
            _log.error(f"Error generando alertas: {e}", exc_info=True)


# ─── Builder Function — usada en ServiceContainer ────────────────────────────

def create_inventory_alert_scheduler(
    inventory_controller,
    interval_minutes: int = 15,
) -> InventoryAlertScheduler:
    """
    Factory para crear y configurar el scheduler.
    Usado en presentation/container.py vía _import().
    """
    return InventoryAlertScheduler(
        inventory_controller=inventory_controller,
        interval_minutes=interval_minutes,
    )
