"""NotificationService birim testleri.

Telegram Bot API mock'lanarak bildirim gönderme ve
konsol logging fonksiyonları test edilir.
"""

import pytest
from unittest.mock import AsyncMock, patch

from src.services.notification_service import NotificationService


@pytest.fixture
def mock_bot():
    """Mock Telegram Bot instance."""
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def admin_id():
    return 123456789


@pytest.fixture
def service(mock_bot, admin_id):
    return NotificationService(bot=mock_bot, admin_id=admin_id)


class TestInit:
    """Constructor testleri."""

    def test_stores_bot(self, service, mock_bot):
        assert service.bot is mock_bot

    def test_stores_admin_id(self, service, admin_id):
        assert service.admin_id == admin_id


class TestNotifyNewEvent:
    """notify_new_event() testleri."""

    @pytest.mark.asyncio
    async def test_sends_message_to_admin(self, service, mock_bot, admin_id):
        url = "https://t.me/KRBZ_VIP_TR/42"
        await service.notify_new_event(url)

        mock_bot.send_message.assert_awaited_once_with(
            admin_id,
            f"Yeni gönderi için izlenme işlemi başlatılıyor:\n{url}",
        )

    @pytest.mark.asyncio
    async def test_message_contains_url(self, service, mock_bot):
        url = "https://t.me/test_channel/99"
        await service.notify_new_event(url)

        sent_message = mock_bot.send_message.call_args[0][1]
        assert url in sent_message

    @pytest.mark.asyncio
    async def test_handles_bot_error_gracefully(self, service, mock_bot, capsys):
        mock_bot.send_message.side_effect = Exception("Telegram API error")
        url = "https://t.me/KRBZ_VIP_TR/1"

        await service.notify_new_event(url)

        captured = capsys.readouterr()
        assert "Bildirim gönderilemedi" in captured.out


class TestNotifyCycleStopped:
    """notify_cycle_stopped() testleri."""

    @pytest.mark.asyncio
    async def test_sends_stop_message_to_admin(self, service, mock_bot, admin_id):
        await service.notify_cycle_stopped()

        mock_bot.send_message.assert_awaited_once_with(
            admin_id,
            "Yeni gönderi algılandı. Önceki işlem durduruluyor...",
        )

    @pytest.mark.asyncio
    async def test_handles_bot_error_gracefully(self, service, mock_bot, capsys):
        mock_bot.send_message.side_effect = Exception("Network error")

        await service.notify_cycle_stopped()

        captured = capsys.readouterr()
        assert "Bildirim gönderilemedi" in captured.out


class TestLogConsole:
    """log_console() testleri."""

    def test_prints_message(self, service, capsys):
        service.log_console("Test mesajı")

        captured = capsys.readouterr()
        assert captured.out.strip() == "Test mesajı"

    def test_prints_empty_message(self, service, capsys):
        service.log_console("")

        captured = capsys.readouterr()
        assert captured.out == "\n"
