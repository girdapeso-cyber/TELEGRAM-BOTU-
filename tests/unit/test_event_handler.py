"""Unit tests for EventHandler.

Batch mantığı, kanal filtreleme, URL oluşturma, ProcessManager ve
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


# --- extract_post_url tests ---


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


# --- Channel filtering tests ---


class TestChannelFiltering:
    """Kanal filtreleme testleri."""

    @pytest.mark.asyncio
    async def test_other_channel_is_ignored(self, handler, process_manager, notification_service):
        """Farklı kanaldan gelen post yoksayılır."""
        update = _make_update("other_channel", 1)
        await handler.handle_channel_post(update, _make_context())
        process_manager.start_batch_cycle.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_channel_post_is_ignored(self, handler, process_manager):
        """channel_post None ise yoksayılır."""
        update = MagicMock()
        update.channel_post = None
        await handler.handle_channel_post(update, _make_context())
        process_manager.start_batch_cycle.assert_not_called()

    @pytest.mark.asyncio
    async def test_target_channel_post_is_added_to_pending(self, handler):
        """Hedef kanaldan gelen post pending listesine eklenir."""
        update = _make_update("KRBZ_VIP_TR", 1)
        await handler.handle_channel_post(update, _make_context())
        assert len(handler._pending_urls) == 1
        assert handler._pending_urls[0] == "https://t.me/KRBZ_VIP_TR/1"


# --- Batch logic tests ---


class TestBatchLogic:
    """Batch mantığı testleri."""

    @pytest.mark.asyncio
    async def test_single_post_does_not_start_cycle(self, handler, process_manager):
        """Tek post geldiğinde döngü başlamaz (batch dolmadı)."""
        update = _make_update("KRBZ_VIP_TR", 1)
        await handler.handle_channel_post(update, _make_context())
        process_manager.start_batch_cycle.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_starts_when_full(self, handler_batch2, process_manager):
        """batch_size=2 iken 2 post gelince döngü başlar."""
        for i in range(2):
            update = _make_update("KRBZ_VIP_TR", i + 1)
            await handler_batch2.handle_channel_post(update, _make_context())

        process_manager.start_batch_cycle.assert_called_once_with([
            "https://t.me/KRBZ_VIP_TR/1",
            "https://t.me/KRBZ_VIP_TR/2",
        ])

    @pytest.mark.asyncio
    async def test_pending_cleared_after_batch(self, handler_batch2):
        """Batch başladıktan sonra pending listesi temizlenir."""
        for i in range(2):
            update = _make_update("KRBZ_VIP_TR", i + 1)
            await handler_batch2.handle_channel_post(update, _make_context())

        assert len(handler_batch2._pending_urls) == 0

    @pytest.mark.asyncio
    async def test_active_urls_set_after_batch(self, handler_batch2):
        """Batch başladıktan sonra active_urls doğru set edilir."""
        for i in range(2):
            update = _make_update("KRBZ_VIP_TR", i + 1)
            await handler_batch2.handle_channel_post(update, _make_context())

        assert handler_batch2._active_urls == [
            "https://t.me/KRBZ_VIP_TR/1",
            "https://t.me/KRBZ_VIP_TR/2",
        ]

    @pytest.mark.asyncio
    async def test_old_cycle_stopped_before_new_batch(
        self, handler_batch2, process_manager, notification_service
    ):
        """Yeni batch başlarken eski döngü durdurulur."""
        # İlk batch
        for i in range(2):
            update = _make_update("KRBZ_VIP_TR", i + 1)
            await handler_batch2.handle_channel_post(update, _make_context())

        # Şimdi döngü çalışıyor
        process_manager.is_cycle_running.return_value = True

        # İkinci batch
        for i in range(2):
            update = _make_update("KRBZ_VIP_TR", i + 3)
            await handler_batch2.handle_channel_post(update, _make_context())

        process_manager.stop_current_cycle.assert_called_once()
        notification_service.notify_cycle_stopped.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_second_batch_has_correct_urls(self, handler_batch2, process_manager):
        """İkinci batch doğru URL'leri içerir."""
        process_manager.is_cycle_running.return_value = False

        # İlk batch
        for i in range(2):
            update = _make_update("KRBZ_VIP_TR", i + 1)
            await handler_batch2.handle_channel_post(update, _make_context())

        process_manager.is_cycle_running.return_value = True

        # İkinci batch
        for i in range(2):
            update = _make_update("KRBZ_VIP_TR", i + 3)
            await handler_batch2.handle_channel_post(update, _make_context())

        # Son çağrı ikinci batch olmalı
        last_call = process_manager.start_batch_cycle.call_args_list[-1]
        assert last_call[0][0] == [
            "https://t.me/KRBZ_VIP_TR/3",
            "https://t.me/KRBZ_VIP_TR/4",
        ]


# --- Notification tests ---


class TestNotificationIntegration:
    """NotificationService entegrasyon testleri."""

    @pytest.mark.asyncio
    async def test_batch_notification_sent(self, handler_batch2, notification_service):
        """Batch başladığında bildirim gönderilir."""
        for i in range(2):
            update = _make_update("KRBZ_VIP_TR", i + 1)
            await handler_batch2.handle_channel_post(update, _make_context())

        notification_service.notify_new_batch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_console_log_on_new_post(self, handler, notification_service):
        """Yeni post geldiğinde konsola log yazılır."""
        update = _make_update("KRBZ_VIP_TR", 70)
        await handler.handle_channel_post(update, _make_context())

        log_calls = [str(c) for c in notification_service.log_console.call_args_list]
        assert any("Yeni post eklendi" in c for c in log_calls)

    @pytest.mark.asyncio
    async def test_console_log_on_batch_stop(
        self, handler_batch2, process_manager, notification_service
    ):
        """Batch durdurulurken konsola log yazılır."""
        # İlk batch
        for i in range(2):
            update = _make_update("KRBZ_VIP_TR", i + 1)
            await handler_batch2.handle_channel_post(update, _make_context())

        process_manager.is_cycle_running.return_value = True

        # İkinci batch tetikle
        for i in range(2):
            update = _make_update("KRBZ_VIP_TR", i + 3)
            await handler_batch2.handle_channel_post(update, _make_context())

        log_calls = [str(c) for c in notification_service.log_console.call_args_list]
        assert any("durduruluyor" in c for c in log_calls)


# --- start_initial_batch tests ---


class TestStartInitialBatch:
    """start_initial_batch() testleri."""

    @pytest.mark.asyncio
    async def test_starts_cycle_with_urls(self, handler, process_manager):
        """Başlangıç batch'i doğru URL'lerle döngü başlatır."""
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
        """Başlangıç batch'i active_urls'i set eder."""
        urls = ["https://t.me/KRBZ_VIP_TR/1", "https://t.me/KRBZ_VIP_TR/2"]
        await handler.start_initial_batch(urls)
        assert handler._active_urls == urls

    @pytest.mark.asyncio
    async def test_empty_urls_does_nothing(self, handler, process_manager):
        """Boş URL listesi ile döngü başlatılmaz."""
        await handler.start_initial_batch([])
        process_manager.start_batch_cycle.assert_not_called()

    @pytest.mark.asyncio
    async def test_truncates_to_batch_size(self, handler_batch2, process_manager):
        """batch_size'dan fazla URL verilirse kesilir."""
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
        """Başlangıç batch'inde bildirim gönderilir."""
        urls = ["https://t.me/KRBZ_VIP_TR/1"]
        await handler.start_initial_batch(urls)
        notification_service.notify_new_batch.assert_awaited_once()
