"""Unit tests for BotCommandHandler.

Gereksinimler: 6.1 (yetkilendirme), 6.2 (yetkisiz yoksayma), 7.1 (hoş geldin mesajı)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.handlers.command_handler import BotCommandHandler


@pytest.fixture
def handler():
    """Yetkili kullanıcıları olan bir BotCommandHandler oluşturur."""
    return BotCommandHandler(
        authorized_users=[111, 222, 333],
        target_channel="KRBZ_VIP_TR",
    )


@pytest.fixture
def make_update():
    """Mock Telegram Update nesnesi oluşturan factory fixture."""

    def _make(user_id: int, first_name: str = "Test"):
        update = MagicMock()
        user = MagicMock()
        user.id = user_id
        user.mention_html.return_value = f'<a href="tg://user?id={user_id}">{first_name}</a>'
        update.effective_user = user
        update.message = MagicMock()
        update.message.reply_html = AsyncMock()
        return update

    return _make


class TestIsAuthorized:
    """is_authorized() metodu testleri."""

    def test_authorized_user_returns_true(self, handler):
        assert handler.is_authorized(111) is True

    def test_unauthorized_user_returns_false(self, handler):
        assert handler.is_authorized(999) is False

    def test_all_authorized_users_accepted(self, handler):
        for uid in [111, 222, 333]:
            assert handler.is_authorized(uid) is True

    def test_empty_authorized_list(self):
        h = BotCommandHandler(authorized_users=[], target_channel="ch")
        assert h.is_authorized(111) is False

    def test_negative_user_id(self, handler):
        assert handler.is_authorized(-1) is False

    def test_zero_user_id(self, handler):
        assert handler.is_authorized(0) is False


class TestHandleStart:
    """handle_start() metodu testleri."""

    @pytest.mark.asyncio
    async def test_authorized_user_gets_welcome(self, handler, make_update):
        update = make_update(user_id=111, first_name="Ali")
        context = MagicMock()

        await handler.handle_start(update, context)

        update.message.reply_html.assert_called_once()
        call_args = update.message.reply_html.call_args[0][0]
        assert "Merhaba" in call_args
        assert "@KRBZ_VIP_TR" in call_args

    @pytest.mark.asyncio
    async def test_unauthorized_user_ignored(self, handler, make_update):
        update = make_update(user_id=999)
        context = MagicMock()

        await handler.handle_start(update, context)

        update.message.reply_html.assert_not_called()

    @pytest.mark.asyncio
    async def test_welcome_contains_user_mention(self, handler, make_update):
        update = make_update(user_id=222, first_name="Veli")
        context = MagicMock()

        await handler.handle_start(update, context)

        call_args = update.message.reply_html.call_args[0][0]
        assert update.effective_user.mention_html() in call_args

    @pytest.mark.asyncio
    async def test_welcome_contains_target_channel(self, handler, make_update):
        update = make_update(user_id=111)
        context = MagicMock()

        await handler.handle_start(update, context)

        call_args = update.message.reply_html.call_args[0][0]
        assert "KRBZ_VIP_TR" in call_args

    @pytest.mark.asyncio
    async def test_no_effective_user_ignored(self, handler):
        update = MagicMock()
        update.effective_user = None
        context = MagicMock()

        await handler.handle_start(update, context)

        update.message.reply_html.assert_not_called()

    @pytest.mark.asyncio
    async def test_custom_target_channel(self, make_update):
        h = BotCommandHandler(authorized_users=[42], target_channel="MY_CHANNEL")
        update = make_update(user_id=42)
        context = MagicMock()

        await h.handle_start(update, context)

        call_args = update.message.reply_html.call_args[0][0]
        assert "@MY_CHANNEL" in call_args
