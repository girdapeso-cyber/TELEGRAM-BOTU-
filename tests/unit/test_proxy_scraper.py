"""Unit tests for ProxyScraper.

Mock API çağrıları ile proxy çekme, dosya kaydetme ve hata toleransı testleri.
Gereksinimler: 3.1, 3.2, 3.3, 9.2
"""

import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.services.proxy_scraper import ProxyScraper


SAMPLE_HTTPS = "1.1.1.1:8080\n2.2.2.2:3128"
SAMPLE_HTTP = "3.3.3.3:80\n4.4.4.4:8888"
SAMPLE_SOCKS5 = "5.5.5.5:1080\n6.6.6.6:1081"


@pytest.fixture
def scraper():
    return ProxyScraper(api_base_url="https://api.proxyscrape.com")


@pytest.fixture(autouse=True)
def cleanup_proxy_files():
    """Remove proxy files after each test."""
    yield
    for f in ("proxies.txt", "socks.txt"):
        if os.path.exists(f):
            os.remove(f)


def _mock_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    return resp


class TestProxyScraperInit:
    def test_default_api_url(self):
        scraper = ProxyScraper()
        assert scraper._api_base_url == "https://api.proxyscrape.com"

    def test_custom_api_url(self):
        scraper = ProxyScraper(api_base_url="https://custom.api.com/")
        assert scraper._api_base_url == "https://custom.api.com"

    def test_trailing_slash_stripped(self):
        scraper = ProxyScraper(api_base_url="https://api.example.com/")
        assert not scraper._api_base_url.endswith("/")


class TestFetchHttpHttpsProxies:
    @patch("src.services.proxy_scraper.requests.get")
    @patch("src.services.proxy_scraper.urllib.request.getproxies", return_value={})
    def test_returns_https_and_http_tuple(self, mock_getproxies, mock_get, scraper):
        mock_get.side_effect = [
            _mock_response(SAMPLE_HTTPS),
            _mock_response(SAMPLE_HTTP),
        ]
        https_proxies, http_proxies = scraper.fetch_http_https_proxies()
        assert https_proxies == SAMPLE_HTTPS
        assert http_proxies == SAMPLE_HTTP

    @patch("src.services.proxy_scraper.requests.get")
    @patch("src.services.proxy_scraper.urllib.request.getproxies", return_value={})
    def test_calls_correct_urls(self, mock_getproxies, mock_get, scraper):
        mock_get.side_effect = [_mock_response(""), _mock_response("")]
        scraper.fetch_http_https_proxies()
        calls = mock_get.call_args_list
        assert "proxytype=https" in calls[0].args[0]
        assert "proxytype=http" in calls[1].args[0]

    @patch("src.services.proxy_scraper.requests.get")
    @patch("src.services.proxy_scraper.urllib.request.getproxies", return_value={})
    def test_raises_on_network_error(self, mock_getproxies, mock_get, scraper):
        mock_get.side_effect = requests.ConnectionError("Connection refused")
        with pytest.raises(requests.ConnectionError):
            scraper.fetch_http_https_proxies()


class TestFetchSocks5Proxies:
    @patch("src.services.proxy_scraper.requests.get")
    @patch("src.services.proxy_scraper.urllib.request.getproxies", return_value={})
    def test_returns_socks5_text(self, mock_getproxies, mock_get, scraper):
        mock_get.return_value = _mock_response(SAMPLE_SOCKS5)
        result = scraper.fetch_socks5_proxies()
        assert result == SAMPLE_SOCKS5

    @patch("src.services.proxy_scraper.requests.get")
    @patch("src.services.proxy_scraper.urllib.request.getproxies", return_value={})
    def test_calls_socks5_url(self, mock_getproxies, mock_get, scraper):
        mock_get.return_value = _mock_response("")
        scraper.fetch_socks5_proxies()
        assert "proxytype=socks5" in mock_get.call_args.args[0]

    @patch("src.services.proxy_scraper.requests.get")
    @patch("src.services.proxy_scraper.urllib.request.getproxies", return_value={})
    def test_raises_on_timeout(self, mock_getproxies, mock_get, scraper):
        mock_get.side_effect = requests.Timeout("Request timed out")
        with pytest.raises(requests.Timeout):
            scraper.fetch_socks5_proxies()


class TestSaveProxies:
    def test_saves_http_https_to_proxies_txt(self, scraper):
        scraper.save_proxies("proxy_data", "socks_data")
        with open("proxies.txt", "r", encoding="utf-8") as f:
            assert f.read() == "proxy_data"

    def test_saves_socks5_to_socks_txt(self, scraper):
        scraper.save_proxies("proxy_data", "socks_data")
        with open("socks.txt", "r", encoding="utf-8") as f:
            assert f.read() == "socks_data"

    def test_overwrites_existing_files(self, scraper):
        scraper.save_proxies("old_data", "old_socks")
        scraper.save_proxies("new_data", "new_socks")
        with open("proxies.txt", "r", encoding="utf-8") as f:
            assert f.read() == "new_data"
        with open("socks.txt", "r", encoding="utf-8") as f:
            assert f.read() == "new_socks"


class TestFetchProxies:
    @patch("src.services.proxy_scraper.requests.get")
    @patch("src.services.proxy_scraper.urllib.request.getproxies", return_value={})
    def test_success_returns_true(self, mock_getproxies, mock_get, scraper):
        mock_get.side_effect = [
            _mock_response(SAMPLE_HTTPS),
            _mock_response(SAMPLE_HTTP),
            _mock_response(SAMPLE_SOCKS5),
        ]
        assert scraper.fetch_proxies() is True

    @patch("src.services.proxy_scraper.requests.get")
    @patch("src.services.proxy_scraper.urllib.request.getproxies", return_value={})
    def test_success_writes_combined_proxies(self, mock_getproxies, mock_get, scraper):
        mock_get.side_effect = [
            _mock_response(SAMPLE_HTTPS),
            _mock_response(SAMPLE_HTTP),
            _mock_response(SAMPLE_SOCKS5),
        ]
        scraper.fetch_proxies()
        with open("proxies.txt", "r", encoding="utf-8") as f:
            content = f.read()
        assert SAMPLE_HTTPS in content
        assert SAMPLE_HTTP in content

    @patch("src.services.proxy_scraper.requests.get")
    @patch("src.services.proxy_scraper.urllib.request.getproxies", return_value={})
    def test_success_writes_socks(self, mock_getproxies, mock_get, scraper):
        mock_get.side_effect = [
            _mock_response(SAMPLE_HTTPS),
            _mock_response(SAMPLE_HTTP),
            _mock_response(SAMPLE_SOCKS5),
        ]
        scraper.fetch_proxies()
        with open("socks.txt", "r", encoding="utf-8") as f:
            assert f.read() == SAMPLE_SOCKS5

    @patch("src.services.proxy_scraper.requests.get")
    @patch("src.services.proxy_scraper.urllib.request.getproxies", return_value={})
    def test_network_error_returns_false(self, mock_getproxies, mock_get, scraper):
        """Req 9.2: Proxy çekme başarısız olursa False döner."""
        mock_get.side_effect = requests.ConnectionError("fail")
        assert scraper.fetch_proxies() is False

    @patch("src.services.proxy_scraper.requests.get")
    @patch("src.services.proxy_scraper.urllib.request.getproxies", return_value={})
    def test_timeout_returns_false(self, mock_getproxies, mock_get, scraper):
        """Req 9.2: Timeout durumunda False döner."""
        mock_get.side_effect = requests.Timeout("timeout")
        assert scraper.fetch_proxies() is False

    @patch("src.services.proxy_scraper.requests.get")
    @patch("src.services.proxy_scraper.urllib.request.getproxies", return_value={})
    def test_partial_failure_returns_false(self, mock_getproxies, mock_get, scraper):
        """First two calls succeed, third fails - should return False."""
        mock_get.side_effect = [
            _mock_response(SAMPLE_HTTPS),
            _mock_response(SAMPLE_HTTP),
            requests.ConnectionError("socks5 failed"),
        ]
        assert scraper.fetch_proxies() is False

    @patch("src.services.proxy_scraper.requests.get")
    @patch("src.services.proxy_scraper.urllib.request.getproxies", return_value={})
    def test_uses_system_proxies(self, mock_getproxies, mock_get, scraper):
        """System proxy support via urllib.request.getproxies()."""
        mock_getproxies.return_value = {"http": "http://sysproxy:8080"}
        mock_get.side_effect = [
            _mock_response(""),
            _mock_response(""),
            _mock_response(""),
        ]
        scraper.fetch_proxies()
        for call in mock_get.call_args_list:
            assert call.kwargs.get("proxies") == {"http": "http://sysproxy:8080"}
