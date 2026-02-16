"""Unit tests for RequestWorker.

URL parsing, stop event kontrolü, hata toleransı ve
ViewProtocolHandler entegrasyonu testleri.

Gereksinimler: 4.4, 4.5, 9.3
"""

import threading
from unittest.mock import MagicMock, call

import pytest

from src.services.request_worker import RequestWorker
from src.services.view_protocol_handler import ViewProtocolHandler


@pytest.fixture
def stop_event():
    return threading.Event()


@pytest.fixture
def mock_handler():
    return MagicMock(spec=ViewProtocolHandler)


VALID_URL = "https://t.me/test_channel/123"
VALID_URL_2 = "https://t.me/other_channel/456"


class TestParseUrl:
    """URL parsing testleri (Gereksinim 9.3)."""

    def test_parses_valid_url(self):
        channel, msg_id = RequestWorker.parse_url(VALID_URL)
        assert channel == "test_channel"
        assert msg_id == "123"

    def test_parses_url_with_different_channel(self):
        channel, msg_id = RequestWorker.parse_url("https://t.me/KRBZ_VIP_TR/999")
        assert channel == "KRBZ_VIP_TR"
        assert msg_id == "999"

    def test_raises_on_short_url(self):
        with pytest.raises(ValueError):
            RequestWorker.parse_url("https://t.me/channel")

    def test_raises_on_empty_string(self):
        with pytest.raises(ValueError):
            RequestWorker.parse_url("")

    def test_raises_on_no_slashes(self):
        with pytest.raises(ValueError):
            RequestWorker.parse_url("not-a-url")

    def test_raises_on_none_input(self):
        with pytest.raises(ValueError):
            RequestWorker.parse_url(None)

    def test_parses_url_with_trailing_slash(self):
        """URL sonunda / varsa msg_id boş olmamalı."""
        channel, msg_id = RequestWorker.parse_url("https://t.me/ch/42/")
        assert channel == "ch"
        assert msg_id == "42"

    def test_raises_on_empty_channel(self):
        with pytest.raises(ValueError):
            RequestWorker.parse_url("https://t.me//123")

    def test_raises_on_empty_msg_id(self):
        with pytest.raises(ValueError):
            RequestWorker.parse_url("https://t.me/channel/")


class TestExecute:
    """execute() metodu testleri (Gereksinim 4.4, 4.5)."""

    def test_calls_view_protocol_for_each_url(self, stop_event, mock_handler):
        """Req 4.4: Her URL için view protocol çalıştırılır."""
        urls = [VALID_URL, VALID_URL_2]
        worker = RequestWorker("http://proxy:8080", urls, stop_event, mock_handler)
        worker.execute()

        assert mock_handler.execute_view_protocol.call_count == 2
        mock_handler.execute_view_protocol.assert_any_call(
            "test_channel", "123", "http://proxy:8080"
        )
        mock_handler.execute_view_protocol.assert_any_call(
            "other_channel", "456", "http://proxy:8080"
        )

    def test_stops_on_stop_event(self, stop_event, mock_handler):
        """Stop event set edildiğinde işlem durur."""
        stop_event.set()
        urls = [VALID_URL, VALID_URL_2]
        worker = RequestWorker("http://proxy:8080", urls, stop_event, mock_handler)
        worker.execute()

        mock_handler.execute_view_protocol.assert_not_called()

    def test_stops_mid_iteration(self, mock_handler):
        """İterasyon ortasında stop event set edilirse durur."""
        stop_event = threading.Event()
        urls = [VALID_URL, VALID_URL_2]

        def set_stop_after_first(*args, **kwargs):
            stop_event.set()
            return True

        mock_handler.execute_view_protocol.side_effect = set_stop_after_first
        worker = RequestWorker("http://proxy:8080", urls, stop_event, mock_handler)
        worker.execute()

        assert mock_handler.execute_view_protocol.call_count == 1

    def test_skips_invalid_url_and_continues(self, stop_event, mock_handler):
        """Req 9.3: Geçersiz URL atlanır, sonraki URL işlenir."""
        urls = ["bad-url", VALID_URL]
        worker = RequestWorker("http://proxy:8080", urls, stop_event, mock_handler)
        worker.execute()

        mock_handler.execute_view_protocol.assert_called_once_with(
            "test_channel", "123", "http://proxy:8080"
        )

    def test_continues_on_view_protocol_exception(self, stop_event, mock_handler):
        """Req 4.5: Network hatası sessizce yoksayılır."""
        mock_handler.execute_view_protocol.side_effect = [
            Exception("network error"),
            True,
        ]
        urls = [VALID_URL, VALID_URL_2]
        worker = RequestWorker("http://proxy:8080", urls, stop_event, mock_handler)
        worker.execute()

        assert mock_handler.execute_view_protocol.call_count == 2

    def test_empty_url_list(self, stop_event, mock_handler):
        """Boş URL listesi ile çalışır, hata vermez."""
        worker = RequestWorker("http://proxy:8080", [], stop_event, mock_handler)
        worker.execute()

        mock_handler.execute_view_protocol.assert_not_called()

    def test_all_invalid_urls(self, stop_event, mock_handler):
        """Tüm URL'ler geçersizse sessizce tamamlanır."""
        urls = ["bad1", "bad2", "bad3"]
        worker = RequestWorker("http://proxy:8080", urls, stop_event, mock_handler)
        worker.execute()

        mock_handler.execute_view_protocol.assert_not_called()


class TestInit:
    """Constructor testleri."""

    def test_stores_proxy(self, stop_event, mock_handler):
        worker = RequestWorker("socks5://1.2.3.4:1080", [VALID_URL], stop_event, mock_handler)
        assert worker._proxy == "socks5://1.2.3.4:1080"

    def test_stores_event_urls(self, stop_event, mock_handler):
        urls = [VALID_URL, VALID_URL_2]
        worker = RequestWorker("http://p:80", urls, stop_event, mock_handler)
        assert worker._event_urls == urls

    def test_stores_stop_event(self, stop_event, mock_handler):
        worker = RequestWorker("http://p:80", [], stop_event, mock_handler)
        assert worker._stop_event is stop_event

    def test_stores_view_handler(self, stop_event, mock_handler):
        worker = RequestWorker("http://p:80", [], stop_event, mock_handler)
        assert worker._view_handler is mock_handler
