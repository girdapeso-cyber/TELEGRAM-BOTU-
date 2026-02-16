"""Unit tests for ThreadCoordinator.

Thread limiti kontrolü, döngü yenileme, stop event ile temiz kapanma,
thread join ve proxy dosya okuma testleri.

Gereksinimler: 3.4, 3.5, 4.1, 4.2, 4.3, 8.2, 8.3, 8.4, 10.1, 10.2
"""

import threading
import time
from unittest.mock import MagicMock, mock_open, patch, call

import pytest

from src.services.proxy_scraper import ProxyScraper
from src.services.thread_coordinator import ThreadCoordinator
from src.services.view_protocol_handler import ViewProtocolHandler


@pytest.fixture
def mock_scraper():
    return MagicMock(spec=ProxyScraper)


@pytest.fixture
def mock_handler():
    return MagicMock(spec=ViewProtocolHandler)


@pytest.fixture
def stop_event():
    return threading.Event()


@pytest.fixture
def coordinator(mock_scraper, mock_handler):
    return ThreadCoordinator(
        max_threads=400,
        proxy_scraper=mock_scraper,
        view_handler=mock_handler,
        cycle_pause=0,  # testlerde bekleme yok
    )


VALID_URL = "https://t.me/test_channel/123"


class TestInit:
    """Constructor testleri."""

    def test_stores_max_threads(self, mock_scraper, mock_handler):
        tc = ThreadCoordinator(200, mock_scraper, mock_handler)
        assert tc._max_threads == 200

    def test_stores_proxy_scraper(self, mock_scraper, mock_handler):
        tc = ThreadCoordinator(400, mock_scraper, mock_handler)
        assert tc._proxy_scraper is mock_scraper

    def test_stores_view_handler(self, mock_scraper, mock_handler):
        tc = ThreadCoordinator(400, mock_scraper, mock_handler)
        assert tc._view_handler is mock_handler

    def test_default_cycle_pause(self, mock_scraper, mock_handler):
        tc = ThreadCoordinator(400, mock_scraper, mock_handler)
        assert tc._cycle_pause == 2

    def test_custom_cycle_pause(self, mock_scraper, mock_handler):
        tc = ThreadCoordinator(400, mock_scraper, mock_handler, cycle_pause=5)
        assert tc._cycle_pause == 5


class TestWaitForThreadSlot:
    """wait_for_thread_slot() testleri (Gereksinim 4.3, 8.2)."""

    @patch("src.services.thread_coordinator.active_count")
    @patch("src.services.thread_coordinator.time.sleep")
    def test_waits_when_over_limit(self, mock_sleep, mock_active):
        """Req 4.3: Aktif thread sayısı limiti aştığında bekler."""
        mock_scraper = MagicMock(spec=ProxyScraper)
        mock_handler = MagicMock(spec=ViewProtocolHandler)
        tc = ThreadCoordinator(10, mock_scraper, mock_handler)

        # İlk çağrıda limit aşılmış, ikincide normal
        mock_active.side_effect = [11, 11, 9]
        tc.wait_for_thread_slot()

        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(0.1)

    @patch("src.services.thread_coordinator.active_count")
    @patch("src.services.thread_coordinator.time.sleep")
    def test_no_wait_when_under_limit(self, mock_sleep, mock_active):
        """Limit altındaysa beklemez."""
        mock_scraper = MagicMock(spec=ProxyScraper)
        mock_handler = MagicMock(spec=ViewProtocolHandler)
        tc = ThreadCoordinator(10, mock_scraper, mock_handler)

        mock_active.return_value = 5
        tc.wait_for_thread_slot()

        mock_sleep.assert_not_called()

    @patch("src.services.thread_coordinator.active_count")
    @patch("src.services.thread_coordinator.time.sleep")
    def test_waits_at_exact_limit(self, mock_sleep, mock_active):
        """Tam limitte beklemez (> kontrolü, >= değil)."""
        mock_scraper = MagicMock(spec=ProxyScraper)
        mock_handler = MagicMock(spec=ViewProtocolHandler)
        tc = ThreadCoordinator(10, mock_scraper, mock_handler)

        mock_active.return_value = 10
        tc.wait_for_thread_slot()

        mock_sleep.assert_not_called()


class TestWaitAllThreads:
    """wait_all_threads() testleri (Gereksinim 8.4)."""

    def test_joins_all_threads(self, coordinator):
        """Req 8.4: Tüm thread'ler join edilir."""
        threads = [MagicMock(spec=threading.Thread) for _ in range(3)]
        coordinator.wait_all_threads(threads)

        for t in threads:
            t.join.assert_called_once()

    def test_empty_thread_list(self, coordinator):
        """Boş liste ile hata vermez."""
        coordinator.wait_all_threads([])


class TestSpawnWorkerThreads:
    """spawn_worker_threads() testleri (Gereksinim 4.2)."""

    @patch("src.services.thread_coordinator.active_count", return_value=1)
    def test_creates_thread_per_proxy(self, mock_active, coordinator, stop_event):
        """Req 4.2: Her proxy için bir thread başlatılır."""
        proxies = ["http://1.1.1.1:80", "http://2.2.2.2:80"]
        threads = coordinator.spawn_worker_threads(proxies, [VALID_URL], stop_event)

        assert len(threads) == 2
        for t in threads:
            assert not t.is_alive()  # kısa işlem, bitmiş olmalı

    @patch("src.services.thread_coordinator.active_count", return_value=1)
    def test_stops_on_stop_event(self, mock_active, coordinator):
        """Stop event set edildiğinde yeni thread başlatmaz."""
        stop = threading.Event()
        stop.set()
        proxies = ["http://1.1.1.1:80", "http://2.2.2.2:80"]
        threads = coordinator.spawn_worker_threads(proxies, [VALID_URL], stop)

        assert len(threads) == 0

    @patch("src.services.thread_coordinator.active_count", return_value=1)
    def test_empty_proxy_list(self, mock_active, coordinator, stop_event):
        """Boş proxy listesi ile boş thread listesi döner."""
        threads = coordinator.spawn_worker_threads([], [VALID_URL], stop_event)
        assert len(threads) == 0


class TestReadProxyFiles:
    """_read_proxy_files() testleri (Gereksinim 9.4)."""

    def test_reads_http_proxies(self, coordinator):
        """proxies.txt'den HTTP proxy'leri okur."""
        proxies_content = "1.1.1.1:80\n2.2.2.2:8080\n"
        with patch("builtins.open", mock_open(read_data=proxies_content)) as m:
            # socks.txt FileNotFoundError fırlatır
            m.side_effect = [
                mock_open(read_data=proxies_content).return_value,
                FileNotFoundError(),
            ]
            result = coordinator._read_proxy_files()

        assert "1.1.1.1:80" in result
        assert "2.2.2.2:8080" in result

    def test_reads_socks_proxies_with_prefix(self, coordinator):
        """socks.txt'den SOCKS5 proxy'leri 'socks5://' prefix ile okur."""
        socks_content = "3.3.3.3:1080\n"
        with patch("builtins.open") as m:
            m.side_effect = [
                FileNotFoundError(),  # proxies.txt yok
                mock_open(read_data=socks_content).return_value,
            ]
            result = coordinator._read_proxy_files()

        assert "socks5://3.3.3.3:1080" in result

    def test_handles_missing_files(self, coordinator):
        """Req 9.4: Dosya bulunamazsa sessizce devam eder."""
        with patch("builtins.open", side_effect=FileNotFoundError()):
            result = coordinator._read_proxy_files()

        assert result == []

    def test_skips_empty_lines(self, coordinator):
        """Boş satırları atlar."""
        content = "1.1.1.1:80\n\n  \n2.2.2.2:80\n"
        with patch("builtins.open") as m:
            m.side_effect = [
                mock_open(read_data=content).return_value,
                FileNotFoundError(),
            ]
            result = coordinator._read_proxy_files()

        assert len(result) == 2

    def test_reads_both_files(self, coordinator):
        """Her iki dosyayı da okur ve birleştirir."""
        proxies_content = "1.1.1.1:80\n"
        socks_content = "2.2.2.2:1080\n"
        with patch("builtins.open") as m:
            m.side_effect = [
                mock_open(read_data=proxies_content).return_value,
                mock_open(read_data=socks_content).return_value,
            ]
            result = coordinator._read_proxy_files()

        assert "1.1.1.1:80" in result
        assert "socks5://2.2.2.2:1080" in result


class TestRunContinuousCycle:
    """run_continuous_cycle() testleri (Gereksinim 10.1, 10.2)."""

    def test_stops_immediately_when_stop_event_set(self, coordinator, mock_scraper):
        """Stop event zaten set ise döngüye girmez."""
        stop = threading.Event()
        stop.set()
        coordinator.run_continuous_cycle([VALID_URL], stop)

        mock_scraper.fetch_proxies.assert_not_called()

    def test_retries_on_proxy_fetch_failure(self, coordinator, mock_scraper):
        """Req 3.5: Proxy çekme başarısız olursa tekrar dener."""
        stop = threading.Event()
        call_count = 0

        def fetch_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return False  # ilk çağrı başarısız
            stop.set()  # ikinci çağrıda durdur
            return True

        mock_scraper.fetch_proxies.side_effect = fetch_side_effect

        with patch("src.services.thread_coordinator.time.sleep"):
            with patch.object(coordinator, "_read_proxy_files", return_value=[]):
                coordinator.run_continuous_cycle([VALID_URL], stop)

        assert mock_scraper.fetch_proxies.call_count == 2

    def test_calls_proxy_scraper_each_cycle(self, coordinator, mock_scraper):
        """Req 3.4: Her döngü başında proxy yenilenir."""
        stop = threading.Event()
        cycle_count = 0

        def fetch_side_effect():
            nonlocal cycle_count
            cycle_count += 1
            if cycle_count >= 2:
                stop.set()
            return True

        mock_scraper.fetch_proxies.side_effect = fetch_side_effect

        with patch.object(coordinator, "_read_proxy_files", return_value=[]):
            with patch.object(coordinator, "spawn_worker_threads", return_value=[]):
                coordinator.run_continuous_cycle([VALID_URL], stop)

        assert mock_scraper.fetch_proxies.call_count >= 2

    def test_spawns_threads_and_waits(self, coordinator, mock_scraper):
        """Thread'ler oluşturulur ve join edilir."""
        stop = threading.Event()
        mock_scraper.fetch_proxies.return_value = True

        mock_threads = [MagicMock(spec=threading.Thread)]

        def spawn_and_stop(*args, **kwargs):
            stop.set()
            return mock_threads

        with patch.object(coordinator, "_read_proxy_files", return_value=["http://1.1.1.1:80"]):
            with patch.object(coordinator, "spawn_worker_threads", side_effect=spawn_and_stop) as mock_spawn:
                with patch.object(coordinator, "wait_all_threads") as mock_wait:
                    coordinator.run_continuous_cycle([VALID_URL], stop)

        mock_spawn.assert_called_once()
        mock_wait.assert_called_once_with(mock_threads)

    def test_full_single_cycle(self, mock_scraper, mock_handler):
        """Tam bir döngü: proxy çek → thread başlat → join → mola."""
        stop = threading.Event()
        tc = ThreadCoordinator(400, mock_scraper, mock_handler, cycle_pause=0)

        cycle_count = 0

        def fetch_side_effect():
            nonlocal cycle_count
            cycle_count += 1
            if cycle_count >= 2:
                stop.set()
            return True

        mock_scraper.fetch_proxies.side_effect = fetch_side_effect

        proxies_content = "1.1.1.1:80\n"
        with patch("builtins.open") as m:
            m.side_effect = [
                mock_open(read_data=proxies_content).return_value,
                FileNotFoundError(),  # socks.txt yok
            ] * 2  # iki döngü için

            with patch("src.services.thread_coordinator.active_count", return_value=1):
                tc.run_continuous_cycle([VALID_URL], stop)

        # En az bir döngü tamamlandı
        assert mock_scraper.fetch_proxies.call_count >= 1

    def test_stop_during_spawn_breaks_loop(self, coordinator, mock_scraper):
        """Spawn sırasında stop event set edilirse döngü durur."""
        stop = threading.Event()
        mock_scraper.fetch_proxies.return_value = True

        def read_and_stop():
            stop.set()
            return ["http://1.1.1.1:80"]

        with patch.object(coordinator, "_read_proxy_files", side_effect=read_and_stop):
            coordinator.run_continuous_cycle([VALID_URL], stop)

        # Stop event set edildiği için döngü durmuş olmalı
        assert stop.is_set()
