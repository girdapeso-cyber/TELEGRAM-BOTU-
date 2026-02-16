"""Tests for Configuration dataclass and config loader."""

import os
from unittest.mock import patch

import pytest

from src.models.config import Configuration
from config import load_configuration, _parse_authorized_users


class TestConfiguration:
    """Unit tests for Configuration dataclass."""

    def test_create_with_required_fields(self):
        config = Configuration(telegram_bot_token="test-token-123")
        assert config.telegram_bot_token == "test-token-123"
        assert config.authorized_users == []
        assert config.target_channel == "KRBZ_VIP_TR"
        assert config.max_threads == 400
        assert config.request_timeout == 10
        assert config.retry_delay == 5
        assert config.cycle_pause == 2

    def test_create_with_all_fields(self):
        config = Configuration(
            telegram_bot_token="token-abc",
            authorized_users=[111, 222],
            target_channel="MY_CHANNEL",
            max_threads=200,
            proxy_api_base_url="https://example.com",
            request_timeout=15,
            retry_delay=3,
            cycle_pause=1,
        )
        assert config.telegram_bot_token == "token-abc"
        assert config.authorized_users == [111, 222]
        assert config.target_channel == "MY_CHANNEL"
        assert config.max_threads == 200
        assert config.proxy_api_base_url == "https://example.com"
        assert config.request_timeout == 15
        assert config.retry_delay == 3
        assert config.cycle_pause == 1

    def test_empty_token_raises_error(self):
        with pytest.raises(ValueError, match="telegram_bot_token is required"):
            Configuration(telegram_bot_token="")

    def test_invalid_max_threads_raises_error(self):
        with pytest.raises(ValueError, match="max_threads must be at least 1"):
            Configuration(telegram_bot_token="token", max_threads=0)

    def test_invalid_request_timeout_raises_error(self):
        with pytest.raises(ValueError, match="request_timeout must be at least 1"):
            Configuration(telegram_bot_token="token", request_timeout=0)

    def test_negative_retry_delay_raises_error(self):
        with pytest.raises(ValueError, match="retry_delay must be non-negative"):
            Configuration(telegram_bot_token="token", retry_delay=-1)

    def test_negative_cycle_pause_raises_error(self):
        with pytest.raises(ValueError, match="cycle_pause must be non-negative"):
            Configuration(telegram_bot_token="token", cycle_pause=-1)


class TestParseAuthorizedUsers:
    """Unit tests for _parse_authorized_users helper."""

    def test_empty_string(self):
        assert _parse_authorized_users("") == []

    def test_whitespace_only(self):
        assert _parse_authorized_users("   ") == []

    def test_single_user(self):
        assert _parse_authorized_users("12345") == [12345]

    def test_multiple_users(self):
        assert _parse_authorized_users("111,222,333") == [111, 222, 333]

    def test_users_with_spaces(self):
        assert _parse_authorized_users(" 111 , 222 , 333 ") == [111, 222, 333]

    def test_trailing_comma(self):
        assert _parse_authorized_users("111,222,") == [111, 222]


class TestLoadConfiguration:
    """Unit tests for load_configuration function."""

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "env-token-xyz"}, clear=False)
    def test_loads_token_from_env(self):
        config = load_configuration()
        assert config.telegram_bot_token == "env-token-xyz"

    @patch.dict(
        os.environ,
        {
            "TELEGRAM_BOT_TOKEN": "tok",
            "AUTHORIZED_USERS": "100,200",
            "TARGET_CHANNEL": "TEST_CH",
            "MAX_THREADS": "50",
            "REQUEST_TIMEOUT": "20",
            "RETRY_DELAY": "10",
            "CYCLE_PAUSE": "3",
        },
        clear=False,
    )
    def test_loads_all_env_vars(self):
        config = load_configuration()
        assert config.telegram_bot_token == "tok"
        assert config.authorized_users == [100, 200]
        assert config.target_channel == "TEST_CH"
        assert config.max_threads == 50
        assert config.request_timeout == 20
        assert config.retry_delay == 10
        assert config.cycle_pause == 3

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_token_raises_error(self):
        with pytest.raises(ValueError):
            load_configuration()
