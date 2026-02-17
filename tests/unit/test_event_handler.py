"""Unit tests for EventHandler.

Kayan pencere mantığı, kanal filtreleme, URL oluşturma, ProcessManager ve
NotificationService entegrasyonunu test eder.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.handlers.event_handler import EventHandler


@pytest.fixture
def process_manager():
    """Mock ProcessManager."""
    pm = MagicMock()
    pm.is_cycle_running.return_value = False
    pm.stop_current_cycle = MagicMock()
    pm.start_new_cycle = MagicMock()
    pm.start_batch_cycle = MagicMock()
    pm.update_urls = MagicMock()
    return pm


@pytest.fixture
def notification_service():
    """Mock NotificationService."""
    ns = MagicMock()
    ns.notify_new_event = AsyncMock()
    ns.notify_new_batch = AsyncMock()
    ns.notify_cycle_stopped = AsyncMock()
    ns.log_console = MagicMock()
    return ns


@pytest.fixture
def handler(process_manager, notification_service):
    """EventHandler with batch_size=4."""
    return EventHandler(
        target_channel="KRBZ_VIP_TR",
        process_manager=process_manager,
        notification_service=notification_service,
        batch_size=4,
    )


@pytest.fixture
def handler_batch2(process_manager, notification_service):
    """EventHandler with batch_size=2 for easier testing."""
    return EventHandler(
        target_channel="KRBZ_VIP_TR",
        process_manager=process_manager,
        notification_service=notification_service,
        batch_size=2,
    )


def _make_update(username: str, message_id: int):
    """Helper: mock Update with channel_post."""
    post = MagicMock()
    post.chat.username = username
    post.message_id = message_id
    update = MagicMock()
    update.channel_post = post
    return update


def _make_context():
    """Helper: mock ContextTypes.DEFAULT_TYPE."""
    return MagicMock()


class TestExtractPostUrl:
    """URL oluşturma testleri."""

    def test_basic_url(self, handler):
        post = MagicMock()
        post.chat.username = "KRBZ_VIP_TR"
        post.message_id = 42
        assert handler.extract_post_url(post) == "https://t.me/KRBZ_VIP_TR/42"

    def test_different_channel_and_id(self, handler):
        post = MagicMock()
        post.chat.username = "test_channel"
        post.message_id = 999
        assert handler.extract_post_url(post) == "https://t.me/test_channel/999"


class TestChannelFiltering:
    """Kanal filtreleme testleri."""

    @pytest.mark.asyncio
    async def test_other_channel_is_ignored(self, handler, process_manager):
        update = _make_update("other_channel", 1)
        await handler.handle_channel_post(update, _make_context())
        process_manager.start_batch_cycle.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_channel_post_is_ignored(self, handler, process_manager):
        update = MagicMock()
        update.channel_post = None
        await handler.handle_channel_post(update, _make_context())
        process_manager.start_batch_cycle.assert_not_called()

    @pytest.mark.asyncio
    async def test_target_channel_post_is_added_to_active(self, handler):
        """Hedef kanaldan gelen post active listesine eklenir."""
        update = _make_update("KRBZ_VIP_TR", 1)
        await handler.handle_channel_post(update, _make_context())
        assert len(handler._active_urls) == 1
        assert handler._active_urls[0] == "https://t.me/KRBZ_VIP_TR/1"


class TestSlidingWindowLogic:
    """Kayan pencere mantığı testleri."""

    @pytest.mark.asyncio
    async def test_first_post_starts_cycle(self, handler, process_manager):
        """İlk post geldiğinde döngü başlar (döngü çalışmıyorsa)."""
        update = _make_update("KRBZ_VIP_TR", 1)
        await handler.handle_channel_post(update, _make_context())
        process_manager.start_batch_cycle.assert_called_once()

    @pytest.mark.asyncio
    async def test_second_post_updates_urls(self, handler, process_manager):
        """Döngü çalışırken yeni post gelince update_urls çağrılır."""
        # İlk post - döngü başlar
        update = _make_update("KRBZ_VIP_TR", 1)
        await handler.handle_channel_post(update, _make_context())

        # Artık döngü çalışıyor
        process_manager.is_cycle_running.return_value = True

        # İkinci post - döngü kesilmez, URL güncellenir
        update2 = _make_update("KRBZ_VIP_TR", 2)
        await handler.handle_channel_post(update2, _make_context())

        process_manager.update_urls.assert_called_once()
        process_manager.stop_current_cycle.assert_not_called()

    @pytest.mark.asyncio
    async def test_window_slides_when_full(self, handler_batch2, process_manager):
        """batch_size=2 iken 3. post gelince en eski çıkar."""
        # İlk 2 post
        for i in range(2):
            update = _make_update("KRBZ_VIP_TR", i + 1)
            await handler_batch2.handle_channel_post(update, _make_context())

        process_manager.is_cycle_running.return_value = True

        # 3. post - pencere kayar
        update3 = _make_update("KRBZ_VIP_TR", 3)
        await handler_batch2.handle_channel_post(update3, _make_context())

        assert handler_batch2._active_urls == [
            "https://t.me/KRBZ_VIP_TR/2",
            "https://t.me/KRBZ_VIP_TR/3",
        ]

    @pytest.mark.asyncio
    async def test_cycle_never_stops_on_new_post(self, handler_batch2, process_manager):
        """Yeni post geldiğinde döngü asla durdurulmaz."""
        for i in range(4):
            if i > 0:
                process_manager.is_cycle_running.return_value = True
            update = _make_update("KRBZ_VIP_TR", i + 1)
            await handler_batch2.handle_channel_post(update, _make_context())

        process_manager.stop_current_cycle.assert_not_called()

    @pytest.mark.asyncio
    async def test_active_urls_correct_after_many_posts(self, handler_batch2, process_manager):
        """Çok sayıda post sonrası aktif pencere son batch_size postu içerir."""
        for i in range(5):
            if i > 0:
                process_manager.is_cycle_running.return_value = True
            update = _make_update("KRBZ_VIP_TR", i + 1)
            await handler_batch2.handle_channel_post(update, _make_context())

        assert handler_batch2._active_urls == [
            "https://t.me/KRBZ_VIP_TR/4",
            "https://t.me/KRBZ_VIP_TR/5",
        ]


class TestNotificationIntegration:
    """NotificationService entegrasyon testleri."""

    @pytest.mark.asyncio
    async def test_batch_notification_on_first_start(self, handler, notification_service):
        """İlk post geldiğinde bildirim gönderilir."""
        update = _make_update("KRBZ_VIP_TR", 1)
        await handler.handle_channel_post(update, _make_context())
        notification_service.notify_new_batch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_console_log_on_new_post(self, handler, notification_service):
        """Yeni post geldiğinde konsola log yazılır."""
        update = _make_update("KRBZ_VIP_TR", 70)
        await handler.handle_channel_post(update, _make_context())
        log_calls = [str(c) for c in notification_service.log_console.call_args_list]
        assert any("Yeni post eklendi" in c for c in log_calls)


class TestStartInitialBatch:
    """start_initial_batch() testleri."""

    @pytest.mark.asyncio
    async def test_starts_cycle_with_urls(self, handler, process_manager):
        urls = [
            "https://t.me/KRBZ_VIP_TR/1",
            "https://t.me/KRBZ_VIP_TR/2",
            "https://t.me/KRBZ_VIP_TR/3",
            "https://t.me/KRBZ_VIP_TR/4",
        ]
        await handler.start_initial_batch(urls)
        process_manager.start_batch_cycle.assert_called_once_with(urls)

    @pytest.mark.asyncio
    async def test_sets_active_urls(self, handler):
        urls = ["https://t.me/KRBZ_VIP_TR/1", "https://t.me/KRBZ_VIP_TR/2"]
        await handler.start_initial_batch(urls)
        assert handler._active_urls == urls

    @pytest.mark.asyncio
    async def test_empty_urls_does_nothing(self, handler, process_manager):
        await handler.start_initial_batch([])
        process_manager.start_batch_cycle.assert_not_called()

    @pytest.mark.asyncio
    async def test_truncates_to_batch_size(self, handler_batch2, process_manager):
        urls = [
            "https://t.me/KRBZ_VIP_TR/1",
            "https://t.me/KRBZ_VIP_TR/2",
            "https://t.me/KRBZ_VIP_TR/3",
        ]
        await handler_batch2.start_initial_batch(urls)
        process_manager.start_batch_cycle.assert_called_once_with([
            "https://t.me/KRBZ_VIP_TR/1",
            "https://t.me/KRBZ_VIP_TR/2",
        ])

    @pytest.mark.asyncio
    async def test_notification_sent(self, handler, notification_service):
        urls = ["https://t.me/KRBZ_VIP_TR/1"]
        await handler.start_initial_batch(urls)
        notification_service.notify_new_batch.assert_awaited_once()
