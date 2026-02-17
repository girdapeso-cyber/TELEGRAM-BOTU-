"""Integration tests for AsyncGhostBooster and ProcessManager asyncio bridge.

Validates: Requirements 10.1, 10.2
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.config import Configuration
from src.ghost_booster.async_ghost_booster import AsyncGhostBooster


def _make_config(**overrides):
    defaults = dict(
        telegram_bot_token="test-token",
        async_concurrency_limit=10,
        health_check_timeout=1.0,
        health_check_concurrency=5,
        proxy_pool_critical_threshold=2,
        jitter_min_ms=10,
        jitter_max_ms=20,
        reaction_enabled=False,
        request_timeout=2,
    )
    defaults.update(overrides)
    return Configuration(**defaults)


class TestAsyncGhostBoosterInit:
    """AsyncGhostBooster'ın tüm bileşenleri doğru oluşturduğunu doğrula."""

    def test_creates_all_components(self):
        config = _make_config()
        booster = AsyncGhostBooster(config)
        assert booster._hunter is not None
        assert booster._checker is not None
        assert booster._pool is not None
        assert booster._worker_pool is not None
        assert booster._reaction_engine is None  # disabled

    def test_reaction_enabled_creates_engine(self):
        config = _make_config(reaction_enabled=True, telegram_api_id=123, telegram_api_hash="abc")
        booster = AsyncGhostBooster(config)
        assert booster._session_manager is not None
        assert booster._reaction_engine is not None

    def test_custom_proxy_sources(self):
        config = _make_config(proxy_sources=["http://example.com/proxies.txt"])
        booster = AsyncGhostBooster(config)
        # Should have custom sources instead of defaults
        source_names = [s.name for s in booster._hunter._sources]
        assert any("Custom" in n for n in source_names)


class TestAsyncGhostBoosterRefill:
    """AsyncGhostBooster._refill_pool'un bileşenleri doğru sırada çağırdığını doğrula."""

    @pytest.mark.asyncio
    async def test_refill_calls_hunt_check_load(self):
        config = _make_config()
        booster = AsyncGhostBooster(config)

        from src.models.proxy_models import ParsedProxy
        mock_proxies = [ParsedProxy(protocol="http", host="1.2.3.4", port=8080)]

        booster._hunter.hunt_all = AsyncMock(return_value=mock_proxies)
        booster._checker.check_all = AsyncMock(return_value=mock_proxies)

        await booster._refill_pool()

        booster._hunter.hunt_all.assert_awaited_once()
        booster._checker.check_all.assert_awaited_once_with(mock_proxies)
        assert booster._pool.size() == 1

    @pytest.mark.asyncio
    async def test_refill_empty_hunt_skips_check(self):
        config = _make_config()
        booster = AsyncGhostBooster(config)

        booster._hunter.hunt_all = AsyncMock(return_value=[])
        booster._checker.check_all = AsyncMock()

        await booster._refill_pool()

        booster._hunter.hunt_all.assert_awaited_once()
        booster._checker.check_all.assert_not_awaited()
        assert booster._pool.size() == 0


class TestProcessManagerAsyncBridge:
    """ProcessManager'ın asyncio köprüsünü doğru kurduğunu doğrula."""

    def test_ghost_booster_created_with_config(self):
        from src.services.thread_coordinator import ThreadCoordinator
        from src.services.process_manager import ProcessManager

        tc = MagicMock(spec=ThreadCoordinator)
        config = _make_config()
        pm = ProcessManager(thread_coordinator=tc, config=config)
        assert pm._ghost_booster is not None

    def test_no_config_uses_thread_coordinator(self):
        from src.services.thread_coordinator import ThreadCoordinator
        from src.services.process_manager import ProcessManager

        tc = MagicMock(spec=ThreadCoordinator)
        pm = ProcessManager(thread_coordinator=tc, config=None)
        assert pm._ghost_booster is None
