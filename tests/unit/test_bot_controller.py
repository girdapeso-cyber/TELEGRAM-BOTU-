"""Unit tests for BotController.

BotController'ın dependency injection, handler kayıt ve start akışını test eder.

Gereksinimler: 1.1 (sürekli dinleme), 6.3 (token güvenliği), 6.4 (authorized users)
"""

import pytest
from unittest.mock import MagicMock, patch, call

from telegram.ext import filters

from src.bot_controller import BotController
from src.models.config import Configuration


@pytest.fixture
def config():
    """Test için Configuration nesnesi."""
    return Configuration(
        telegram_bot_token="test-token-123",
        authorized_users=[111, 222],
        target_channel="TEST_CHANNEL",
        max_threads=10,
        proxy_api_base_url="https://api.proxyscrape.com",
        request_timeout=10,
        retry_delay=5,
        cycle_pause=2,
        batch_size=4,
    )


@pytest.fixture
def mock_application():
    """Mock Application builder chain."""
    app = MagicMock()
    app.bot = MagicMock()
    builder = MagicMock()
    builder.token.return_value = builder
    builder.build.return_value = app
    return builder, app


class TestBotControllerInit:
    """__init__() testleri - dependency injection ve wiring."""

    @patch("src.bot_controller.Application")
    def test_builds_application_with_token(self, mock_app_cls, config, mock_application):
        builder, app = mock_application
        mock_app_cls.builder.return_value = builder

        controller = BotController(config)

        mock_app_cls.builder.assert_called_once()
        builder.token.assert_called_once_with("test-token-123")
        builder.build.assert_called_once()

    @patch("src.bot_controller.Application")
    def test_stores_config(self, mock_app_cls, config, mock_application):
        builder, app = mock_application
        mock_app_cls.builder.return_value = builder

        controller = BotController(config)

        assert controller.config is config

    @patch("src.bot_controller.Application")
    def test_stores_application(self, mock_app_cls, config, mock_application):
        builder, app = mock_application
        mock_app_cls.builder.return_value = builder

        controller = BotController(config)

        assert controller.application is app

    @patch("src.bot_controller.Application")
    def test_creates_command_handler_with_authorized_users(self, mock_app_cls, config, mock_application):
        builder, app = mock_application
        mock_app_cls.builder.return_value = builder

        controller = BotController(config)

        assert controller.command_handler.authorized_users == [111, 222]
        assert controller.command_handler.target_channel == "TEST_CHANNEL"

    @patch("src.bot_controller.Application")
    def test_creates_event_handler_with_target_channel(self, mock_app_cls, config, mock_application):
        builder, app = mock_application
        mock_app_cls.builder.return_value = builder

        controller = BotController(config)

        assert controller.event_handler.target_channel == "TEST_CHANNEL"

    @patch("src.bot_controller.Application")
    def test_event_handler_has_process_manager(self, mock_app_cls, config, mock_application):
        builder, app = mock_application
        mock_app_cls.builder.return_value = builder

        controller = BotController(config)

        assert controller.event_handler.process_manager is not None

    @patch("src.bot_controller.Application")
    def test_event_handler_has_notification_service(self, mock_app_cls, config, mock_application):
        builder, app = mock_application
        mock_app_cls.builder.return_value = builder

        controller = BotController(config)

        assert controller.event_handler.notification_service is not None

    @patch("src.bot_controller.Application")
    def test_notification_service_uses_app_bot(self, mock_app_cls, config, mock_application):
        builder, app = mock_application
        mock_app_cls.builder.return_value = builder

        controller = BotController(config)

        ns = controller.event_handler.notification_service
        assert ns.bot is app.bot

    @patch("src.bot_controller.Application")
    def test_notification_service_uses_first_admin(self, mock_app_cls, config, mock_application):
        builder, app = mock_application
        mock_app_cls.builder.return_value = builder

        controller = BotController(config)

        ns = controller.event_handler.notification_service
        assert ns.admin_id == 111

    @patch("src.bot_controller.Application")
    def test_empty_authorized_users_admin_id_zero(self, mock_app_cls, mock_application):
        builder, app = mock_application
        mock_app_cls.builder.return_value = builder

        cfg = Configuration(
            telegram_bot_token="tok",
            authorized_users=[],
            target_channel="CH",
        )
        controller = BotController(cfg)

        ns = controller.event_handler.notification_service
        assert ns.admin_id == 0


class TestRegisterHandlers:
    """register_handlers() testleri."""

    @patch("src.bot_controller.Application")
    def test_registers_two_handlers(self, mock_app_cls, config, mock_application):
        builder, app = mock_application
        mock_app_cls.builder.return_value = builder

        controller = BotController(config)
        controller.register_handlers()

        assert app.add_handler.call_count == 2

    @patch("src.bot_controller.Application")
    def test_registers_start_command_handler(self, mock_app_cls, config, mock_application):
        builder, app = mock_application
        mock_app_cls.builder.return_value = builder

        controller = BotController(config)
        controller.register_handlers()

        first_handler = app.add_handler.call_args_list[0][0][0]
        assert isinstance(first_handler, MagicMock) or first_handler is not None

    @patch("src.bot_controller.Application")
    @patch("src.bot_controller.CommandHandler")
    @patch("src.bot_controller.MessageHandler")
    def test_command_handler_uses_start(self, mock_msg_handler, mock_cmd_handler, mock_app_cls, config, mock_application):
        builder, app = mock_application
        mock_app_cls.builder.return_value = builder

        controller = BotController(config)
        controller.register_handlers()

        mock_cmd_handler.assert_called_once_with(
            "start", controller.command_handler.handle_start
        )

    @patch("src.bot_controller.Application")
    @patch("src.bot_controller.CommandHandler")
    @patch("src.bot_controller.MessageHandler")
    def test_message_handler_uses_channel_filter(self, mock_msg_handler, mock_cmd_handler, mock_app_cls, config, mock_application):
        builder, app = mock_application
        mock_app_cls.builder.return_value = builder

        controller = BotController(config)
        controller.register_handlers()

        mock_msg_handler.assert_called_once_with(
            filters.ChatType.CHANNEL,
            controller.event_handler.handle_channel_post,
        )


class TestStart:
    """start() testleri."""

    @patch("src.bot_controller.Application")
    def test_start_calls_register_handlers_then_run_polling(self, mock_app_cls, config, mock_application):
        builder, app = mock_application
        mock_app_cls.builder.return_value = builder

        controller = BotController(config)
        controller.register_handlers = MagicMock()

        controller.start()

        controller.register_handlers.assert_called_once()
        app.run_polling.assert_called_once()

    @patch("src.bot_controller.Application")
    def test_start_prints_channel_info(self, mock_app_cls, config, mock_application, capsys):
        builder, app = mock_application
        mock_app_cls.builder.return_value = builder

        controller = BotController(config)
        controller.register_handlers = MagicMock()

        controller.start()

        captured = capsys.readouterr()
        assert "TEST_CHANNEL" in captured.out
