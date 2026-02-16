"""Unit tests for ViewProtocolHandler.

Mock HTTP istekleri ile her protokol adımını test eder:
cookie parsing, data-view extraction, view registration, timeout ve hata toleransı.

Gereksinimler: 5.1, 5.2, 5.3, 5.4, 5.5, 9.1, 9.5
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.services.view_protocol_handler import ViewProtocolHandler


@pytest.fixture
def handler():
    return ViewProtocolHandler(timeout=10)


def _mock_response(text: str = "", headers: dict = None, status_code: int = 200):
    resp = MagicMock()
    resp.text = text
    resp.headers = headers or {}
    resp.status_code = status_code
    return resp


SAMPLE_COOKIE = "stel_ssid=abc123def456"
SAMPLE_HTML_WITH_KEY = '<div data-view="eyJwIjoiMTIzIn0="></div>'
SAMPLE_HTML_NO_KEY = "<div>no view key here</div>"


class TestViewProtocolHandlerInit:
    def test_default_timeout(self):
        h = ViewProtocolHandler()
        assert h._timeout == 10

    def test_custom_timeout(self):
        h = ViewProtocolHandler(timeout=5)
        assert h._timeout == 5


class TestFetchPageAndCookie:
    def test_extracts_cookie_from_set_cookie_header(self, handler):
        session = MagicMock()
        session.get.return_value = _mock_response(
            headers={"set-cookie": "stel_ssid=abc123; Path=/; HttpOnly"}
        )
        result = handler.fetch_page_and_cookie(
            "test_channel", "42", {"http": "http://proxy:8080", "https": "http://proxy:8080"}, session
        )
        assert result == "stel_ssid=abc123"

    def test_calls_correct_url(self, handler):
        session = MagicMock()
        session.get.return_value = _mock_response(
            headers={"set-cookie": "stel_ssid=x; Path=/"}
        )
        handler.fetch_page_and_cookie(
            "my_channel", "99", {"http": "http://p:80", "https": "http://p:80"}, session
        )
        session.get.assert_called_once_with(
            "https://t.me/my_channel/99",
            timeout=10,
            proxies={"http": "http://p:80", "https": "http://p:80"},
        )

    def test_returns_none_when_no_set_cookie(self, handler):
        session = MagicMock()
        session.get.return_value = _mock_response(headers={})
        result = handler.fetch_page_and_cookie(
            "ch", "1", {"http": "http://p:80", "https": "http://p:80"}, session
        )
        assert result is None

    def test_returns_none_on_empty_cookie(self, handler):
        session = MagicMock()
        session.get.return_value = _mock_response(headers={"set-cookie": ""})
        result = handler.fetch_page_and_cookie(
            "ch", "1", {"http": "http://p:80", "https": "http://p:80"}, session
        )
        assert result is None

    def test_returns_none_on_timeout(self, handler):
        """Req 5.5, 9.1: Timeout durumunda None döner."""
        session = MagicMock()
        session.get.side_effect = requests.Timeout("timed out")
        result = handler.fetch_page_and_cookie(
            "ch", "1", {"http": "http://p:80", "https": "http://p:80"}, session
        )
        assert result is None

    def test_returns_none_on_connection_error(self, handler):
        """Req 9.5: Network hatalarını sessizce işler."""
        session = MagicMock()
        session.get.side_effect = requests.ConnectionError("refused")
        result = handler.fetch_page_and_cookie(
            "ch", "1", {"http": "http://p:80", "https": "http://p:80"}, session
        )
        assert result is None


class TestFetchViewKey:
    def test_extracts_data_view_key(self, handler):
        session = MagicMock()
        session.post.return_value = _mock_response(text=SAMPLE_HTML_WITH_KEY)
        result = handler.fetch_view_key(
            "ch", "1", SAMPLE_COOKIE,
            {"http": "http://p:80", "https": "http://p:80"}, session
        )
        assert result == "eyJwIjoiMTIzIn0="

    def test_sends_correct_headers_and_data(self, handler):
        session = MagicMock()
        session.post.return_value = _mock_response(text=SAMPLE_HTML_NO_KEY)
        handler.fetch_view_key(
            "test_ch", "55", "my_cookie",
            {"http": "http://p:80", "https": "http://p:80"}, session
        )
        call_kwargs = session.post.call_args
        assert call_kwargs.args[0] == "https://t.me/test_ch/55?embed=1"
        headers = call_kwargs.kwargs["headers"]
        assert headers["Cookie"] == "my_cookie"
        assert headers["Host"] == "t.me"
        assert headers["Origin"] == "https://t.me"
        assert headers["Referer"] == "https://t.me/test_ch/55?embed=1"
        assert call_kwargs.kwargs["json"] == {"_rl": "1"}

    def test_returns_none_when_no_data_view(self, handler):
        session = MagicMock()
        session.post.return_value = _mock_response(text=SAMPLE_HTML_NO_KEY)
        result = handler.fetch_view_key(
            "ch", "1", SAMPLE_COOKIE,
            {"http": "http://p:80", "https": "http://p:80"}, session
        )
        assert result is None

    def test_returns_none_on_timeout(self, handler):
        """Req 5.5, 9.1: Timeout durumunda None döner."""
        session = MagicMock()
        session.post.side_effect = requests.Timeout("timed out")
        result = handler.fetch_view_key(
            "ch", "1", SAMPLE_COOKIE,
            {"http": "http://p:80", "https": "http://p:80"}, session
        )
        assert result is None

    def test_returns_none_on_connection_error(self, handler):
        """Req 9.5: Network hatalarını sessizce işler."""
        session = MagicMock()
        session.post.side_effect = requests.ConnectionError("refused")
        result = handler.fetch_view_key(
            "ch", "1", SAMPLE_COOKIE,
            {"http": "http://p:80", "https": "http://p:80"}, session
        )
        assert result is None

    def test_returns_none_on_empty_key(self, handler):
        session = MagicMock()
        session.post.return_value = _mock_response(text='data-view=""')
        result = handler.fetch_view_key(
            "ch", "1", SAMPLE_COOKIE,
            {"http": "http://p:80", "https": "http://p:80"}, session
        )
        assert result is None


class TestRegisterView:
    def test_sends_get_with_correct_url_and_headers(self, handler):
        session = MagicMock()
        session.get.return_value = _mock_response()
        handler.register_view(
            "viewkey123", "ch", "1", "my_cookie",
            {"http": "http://p:80", "https": "http://p:80"}, session
        )
        call_kwargs = session.get.call_args
        assert call_kwargs.args[0] == "https://t.me/v/?views=viewkey123"
        headers = call_kwargs.kwargs["headers"]
        assert headers["Cookie"] == "my_cookie"
        assert headers["X-Requested-With"] == "XMLHttpRequest"
        assert headers["Referer"] == "https://t.me/ch/1?embed=1"

    def test_returns_true_on_success(self, handler):
        session = MagicMock()
        session.get.return_value = _mock_response()
        result = handler.register_view(
            "key", "ch", "1", "cookie",
            {"http": "http://p:80", "https": "http://p:80"}, session
        )
        assert result is True

    def test_returns_false_on_timeout(self, handler):
        """Req 5.5, 9.1: Timeout durumunda False döner."""
        session = MagicMock()
        session.get.side_effect = requests.Timeout("timed out")
        result = handler.register_view(
            "key", "ch", "1", "cookie",
            {"http": "http://p:80", "https": "http://p:80"}, session
        )
        assert result is False

    def test_returns_false_on_connection_error(self, handler):
        """Req 9.5: Network hatalarını sessizce işler."""
        session = MagicMock()
        session.get.side_effect = requests.ConnectionError("refused")
        result = handler.register_view(
            "key", "ch", "1", "cookie",
            {"http": "http://p:80", "https": "http://p:80"}, session
        )
        assert result is False


class TestExecuteViewProtocol:
    @patch.object(ViewProtocolHandler, "register_view", return_value=True)
    @patch.object(ViewProtocolHandler, "fetch_view_key", return_value="viewkey")
    @patch.object(ViewProtocolHandler, "fetch_page_and_cookie", return_value="cookie_val")
    def test_full_protocol_success(self, mock_cookie, mock_key, mock_register, handler):
        result = handler.execute_view_protocol("ch", "1", "http://proxy:8080")
        assert result is True
        mock_cookie.assert_called_once()
        mock_key.assert_called_once()
        mock_register.assert_called_once()

    @patch.object(ViewProtocolHandler, "fetch_page_and_cookie", return_value=None)
    def test_returns_false_when_cookie_fails(self, mock_cookie, handler):
        result = handler.execute_view_protocol("ch", "1", "http://proxy:8080")
        assert result is False

    @patch.object(ViewProtocolHandler, "fetch_view_key", return_value=None)
    @patch.object(ViewProtocolHandler, "fetch_page_and_cookie", return_value="cookie")
    def test_returns_false_when_view_key_fails(self, mock_cookie, mock_key, handler):
        result = handler.execute_view_protocol("ch", "1", "http://proxy:8080")
        assert result is False

    @patch.object(ViewProtocolHandler, "register_view", return_value=False)
    @patch.object(ViewProtocolHandler, "fetch_view_key", return_value="key")
    @patch.object(ViewProtocolHandler, "fetch_page_and_cookie", return_value="cookie")
    def test_returns_false_when_register_fails(self, mock_cookie, mock_key, mock_reg, handler):
        result = handler.execute_view_protocol("ch", "1", "http://proxy:8080")
        assert result is False

    def test_builds_correct_proxy_dict(self, handler):
        """Verifies proxy string is converted to dict for both http and https."""
        with patch.object(handler, "fetch_page_and_cookie", return_value=None) as mock_fetch:
            handler.execute_view_protocol("ch", "1", "socks5://1.2.3.4:1080")
            call_args = mock_fetch.call_args
            proxy_dict = call_args[0][2]  # third positional arg
            assert proxy_dict == {
                "http": "socks5://1.2.3.4:1080",
                "https": "socks5://1.2.3.4:1080",
            }

    @patch.object(ViewProtocolHandler, "fetch_page_and_cookie", side_effect=Exception("unexpected"))
    def test_returns_false_on_unexpected_exception(self, mock_cookie, handler):
        """Req 9.5: Tüm hatalar yakalanır."""
        result = handler.execute_view_protocol("ch", "1", "http://proxy:8080")
        assert result is False

    @patch.object(ViewProtocolHandler, "register_view", return_value=True)
    @patch.object(ViewProtocolHandler, "fetch_view_key", return_value="key")
    @patch.object(ViewProtocolHandler, "fetch_page_and_cookie", return_value="cookie")
    def test_sequential_execution_order(self, mock_cookie, mock_key, mock_register, handler):
        """Req 5.1-5.4: Adımlar sıralı çalıştırılır, her adım öncekinin çıktısını kullanır."""
        handler.execute_view_protocol("test_ch", "42", "http://p:80")

        # Cookie step receives channel and msg_id
        cookie_args = mock_cookie.call_args[0]
        assert cookie_args[0] == "test_ch"
        assert cookie_args[1] == "42"

        # View key step receives the cookie from previous step
        key_args = mock_key.call_args[0]
        assert key_args[0] == "test_ch"
        assert key_args[1] == "42"
        assert key_args[2] == "cookie"  # cookie from fetch_page_and_cookie

        # Register step receives the view key from previous step
        reg_args = mock_register.call_args[0]
        assert reg_args[0] == "key"  # key from fetch_view_key
        assert reg_args[3] == "cookie"  # cookie carried through
