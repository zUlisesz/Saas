# tests/unit/test_container.py
#
# Tests del ServiceContainer — Fase 6 (H10).
#
# PROPÓSITO:
#   Detectar imports rotos, nombres mal escritos o servicios olvidados
#   antes de ejecutar la app. Un test de 20 líneas que evita el clásico
#   "KeyError: 'recharge_controller'" en runtime.
#
# NOTA: wire() registra factories (lambdas), no instancia servicios.
#   has() solo consulta el dict de factories — sin DB, sin red.

import pytest
from unittest.mock import MagicMock

from presentation.container import ServiceContainer


_REPOS = [
    "auth_repo", "tenant_repo", "product_repo", "category_repo",
    "sale_repo", "inventory_repo", "alert_repo", "event_repo",
    "analytics_repo", "ticket_repo", "recharge_repo",
]
_SERVICES = [
    "auth_service", "event_service", "product_service", "category_service",
    "analytics_service", "ticket_service", "inventory_service", "alert_service",
    "sale_service", "recharge_service",
]
_USE_CASES = [
    "register_use_case", "create_product_use_case", "create_sale_use_case",
    "process_recharge_use_case",
]
_CONTROLLERS = [
    "auth_controller", "product_controller", "category_controller",
    "sale_controller", "analytics_controller", "inventory_controller",
    "recharge_controller",
]
_SCHEDULERS = ["inventory_alert_scheduler"]

ALL_SERVICES = _REPOS + _SERVICES + _USE_CASES + _CONTROLLERS + _SCHEDULERS


def _wired_container() -> ServiceContainer:
    container = ServiceContainer()
    container.set_app(MagicMock())
    container.wire()
    return container


class TestServiceContainerWiring:

    def test_wire_registers_all_repos(self):
        c = _wired_container()
        for name in _REPOS:
            assert c.has(name), f"repo '{name}' no registrado"

    def test_wire_registers_all_services(self):
        c = _wired_container()
        for name in _SERVICES:
            assert c.has(name), f"service '{name}' no registrado"

    def test_wire_registers_all_use_cases(self):
        c = _wired_container()
        for name in _USE_CASES:
            assert c.has(name), f"use case '{name}' no registrado"

    def test_wire_registers_all_controllers(self):
        c = _wired_container()
        for name in _CONTROLLERS:
            assert c.has(name), f"controller '{name}' no registrado"

    def test_wire_is_idempotent(self):
        """Llamar wire() dos veces no duplica ni rompe el registro."""
        c = _wired_container()
        c.wire()
        assert c.has("recharge_controller")

    def test_get_unknown_raises_key_error(self):
        c = _wired_container()
        with pytest.raises(KeyError, match="no está registrado"):
            c.get("servicio_inexistente")

    def test_register_overrides_factory_and_singleton(self):
        """register() invalida el singleton existente."""
        c = ServiceContainer()
        sentinel_a = object()
        sentinel_b = object()

        c.register("x", lambda: sentinel_a)
        assert c.get("x") is sentinel_a

        c.register("x", lambda: sentinel_b)
        assert c.get("x") is sentinel_b

    def test_registered_returns_sorted_names(self):
        c = ServiceContainer()
        c.register("z_svc", lambda: None)
        c.register("a_svc", lambda: None)
        result = c.registered()
        assert result == sorted(result)

    def test_reset_clears_singletons_keeps_factories(self):
        c = ServiceContainer()
        created = []
        c.register("svc", lambda: created.append(1) or object())

        c.get("svc")
        assert len(created) == 1

        c.reset()
        c.get("svc")
        assert len(created) == 2
