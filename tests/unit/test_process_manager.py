"""Unit tests for ProcessManager.

Döngü başlatma/durdurma, durum kontrolü ve thread-safety testleri.
Gereksinimler: 2.1, 2.2, 2.3, 2.4
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.models.data_models import CycleState, EventInfo
from src.services.process_manager import ProcessManager
from src.services.thread_coordinator import ThreadCoordinator


@pytest.fixture
def mock_coordinator():
    """ThreadCoordinator mock'u oluşturur."""
    coordinator = MagicMock(spec=ThreadCoordinator)
    # run_continuous_cycle varsayılan olarak stop_event beklesin
    def fake_run(event_urls, stop_event):
        stop_event.wait()
    coordinator.run_continuous_cycle.side_effect = fake_run
    return coordinator


@pytest.fixture
def process_manager(mock_coordinator):
    """ProcessManager instance'ı oluşturur."""
    return ProcessManager(mock_coordinator)


class TestProcessManagerInit:
    """ProcessManager başlatma testleri."""

    def test_initial_state_no_cycle(self, process_manager):
        """Başlangıçta aktif döngü olmamalı."""
        assert process_manager.is_cycle_running() is False

    def test_initial_cycle_is_none(self, process_manager):
        """Başlangıçta _current_cycle None olmalı."""
        assert process_manager._current_cycle is None


class TestStartNewCycle:
    """start_new_cycle() testleri."""

    def test_starts_cycle(self, process_manager, mock_coordinator):
        """Yeni döngü başlatıldığında is_cycle_running True döner."""
        process_manager.start_new_cycle("https://t.me/test_channel/123")
        time.sleep(0.1)  # Thread'in başlaması için kısa bekleme
        assert process_manager.is_cycle_running() is True

    def test_coordinator_called_with_url(self, process_manager, mock_coordinator):
        """ThreadCoordinator doğru URL ile çağrılmalı."""
        process_manager.start_new_cycle("https://t.me/test_channel/456")
        time.sleep(0.1)
        mock_coordinator.run_continuous_cycle.assert_called_once()
        call_args = mock_coordinator.run_continuous_cycle.call_args
        assert call_args.kwargs["event_urls"] == ["https://t.me/test_channel/456"]

    def test_cycle_state_created(self, process_manager):
        """CycleState doğru oluşturulmalı."""
        process_manager.start_new_cycle("https://t.me/channel/789")
        time.sleep(0.1)
        cycle = process_manager._current_cycle
        assert cycle is not None
        assert cycle.event_info.url == "https://t.me/channel/789"
        assert cycle.event_info.channel == "channel"
        assert cycle.event_info.message_id == "789"
        assert cycle.thread_handle is not None

    def test_stops_old_cycle_before_starting_new(self, process_manager, mock_coordinator):
        """Yeni döngü başlatılırken eski döngü durdurulmalı (Gereksinim 2.1)."""
        process_manager.start_new_cycle("https://t.me/channel/1")
        time.sleep(0.1)
        old_cycle = process_manager._current_cycle

        process_manager.start_new_cycle("https://t.me/channel/2")
        time.sleep(0.1)

        # Eski döngünün stop event'i set edilmiş olmalı
        assert old_cycle.stop_event.is_set()
        # Yeni döngü çalışıyor olmalı
        assert process_manager.is_cycle_running() is True
        new_cycle = process_manager._current_cycle
        assert new_cycle.event_info.message_id == "2"

    def test_only_one_cycle_at_a_time(self, process_manager):
        """Aynı anda yalnızca bir döngü çalışmalı (Gereksinim 2.4)."""
        process_manager.start_new_cycle("https://t.me/channel/1")
        time.sleep(0.1)
        process_manager.start_new_cycle("https://t.me/channel/2")
        time.sleep(0.1)
        process_manager.start_new_cycle("https://t.me/channel/3")
        time.sleep(0.1)

        # Sadece son döngü aktif olmalı
        assert process_manager._current_cycle.event_info.message_id == "3"
        assert process_manager.is_cycle_running() is True

    def test_new_cycle_after_stop(self, process_manager):
        """Durdurulduktan sonra yeni döngü başlatılabilmeli (Gereksinim 2.3)."""
        process_manager.start_new_cycle("https://t.me/channel/1")
        time.sleep(0.1)
        process_manager.stop_current_cycle()
        time.sleep(0.1)

        process_manager.start_new_cycle("https://t.me/channel/2")
        time.sleep(0.1)
        assert process_manager.is_cycle_running() is True
        assert process_manager._current_cycle.event_info.message_id == "2"


class TestStopCurrentCycle:
    """stop_current_cycle() testleri."""

    def test_stop_running_cycle(self, process_manager):
        """Çalışan döngü durdurulabilmeli (Gereksinim 2.2)."""
        process_manager.start_new_cycle("https://t.me/channel/1")
        time.sleep(0.1)
        assert process_manager.is_cycle_running() is True

        process_manager.stop_current_cycle()
        time.sleep(0.2)
        assert process_manager.is_cycle_running() is False

    def test_stop_sets_stop_event(self, process_manager):
        """stop_current_cycle stop_event'i set etmeli."""
        process_manager.start_new_cycle("https://t.me/channel/1")
        time.sleep(0.1)
        cycle = process_manager._current_cycle

        process_manager.stop_current_cycle()
        assert cycle.stop_event.is_set()

    def test_stop_when_no_cycle(self, process_manager):
        """Döngü yokken stop çağrılırsa hata vermemeli."""
        process_manager.stop_current_cycle()  # Hata vermemeli

    def test_stop_already_stopped_cycle(self, process_manager):
        """Zaten durmuş döngüyü tekrar durdurmak hata vermemeli."""
        process_manager.start_new_cycle("https://t.me/channel/1")
        time.sleep(0.1)
        process_manager.stop_current_cycle()
        time.sleep(0.1)
        process_manager.stop_current_cycle()  # İkinci kez - hata vermemeli

    def test_stop_joins_thread_with_timeout(self, process_manager, mock_coordinator):
        """Thread join 5 saniye timeout ile çağrılmalı (Gereksinim 2.2)."""
        # Uzun süren bir döngü simüle et
        long_event = threading.Event()

        def slow_run(event_urls, stop_event):
            long_event.wait(timeout=10)

        mock_coordinator.run_continuous_cycle.side_effect = slow_run

        process_manager.start_new_cycle("https://t.me/channel/1")
        time.sleep(0.1)
        thread = process_manager._current_cycle.thread_handle

        start = time.time()
        # Signal long_event so thread finishes quickly
        long_event.set()
        process_manager.stop_current_cycle()
        elapsed = time.time() - start

        # 5 saniyeden kısa sürmeli (thread hemen bitmeli)
        assert elapsed < 5


class TestIsCycleRunning:
    """is_cycle_running() testleri."""

    def test_false_when_no_cycle(self, process_manager):
        """Döngü yokken False döner."""
        assert process_manager.is_cycle_running() is False

    def test_true_when_cycle_active(self, process_manager):
        """Döngü aktifken True döner."""
        process_manager.start_new_cycle("https://t.me/channel/1")
        time.sleep(0.1)
        assert process_manager.is_cycle_running() is True

    def test_false_after_cycle_completes(self, process_manager, mock_coordinator):
        """Döngü tamamlandıktan sonra False döner."""
        # Hemen biten bir döngü
        mock_coordinator.run_continuous_cycle.side_effect = lambda **kwargs: None

        process_manager.start_new_cycle("https://t.me/channel/1")
        time.sleep(0.3)  # Thread'in bitmesi için bekle
        assert process_manager.is_cycle_running() is False

    def test_false_after_stop(self, process_manager):
        """Durdurulduktan sonra False döner."""
        process_manager.start_new_cycle("https://t.me/channel/1")
        time.sleep(0.1)
        process_manager.stop_current_cycle()
        time.sleep(0.2)
        assert process_manager.is_cycle_running() is False


class TestParseEventInfo:
    """_parse_event_info() testleri."""

    def test_standard_url(self):
        """Standart Telegram URL'i doğru parse edilmeli."""
        info = ProcessManager._parse_event_info("https://t.me/KRBZ_VIP_TR/123")
        assert info.channel == "KRBZ_VIP_TR"
        assert info.message_id == "123"
        assert info.url == "https://t.me/KRBZ_VIP_TR/123"

    def test_trailing_slash(self):
        """Sondaki slash ile URL doğru parse edilmeli."""
        info = ProcessManager._parse_event_info("https://t.me/channel/456/")
        assert info.channel == "channel"
        assert info.message_id == "456"

    def test_timestamp_set(self):
        """Timestamp ayarlanmış olmalı."""
        before = time.time()
        info = ProcessManager._parse_event_info("https://t.me/ch/1")
        after = time.time()
        assert before <= info.timestamp <= after


class TestThreadSafety:
    """Thread-safety testleri."""

    def test_concurrent_start_cycles(self, mock_coordinator):
        """Birden fazla thread aynı anda start_new_cycle çağırabilmeli."""
        pm = ProcessManager(mock_coordinator)
        errors = []

        def start_cycle(url):
            try:
                pm.start_new_cycle(url)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(5):
            t = threading.Thread(target=start_cycle, args=(f"https://t.me/ch/{i}",))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        # Sonunda sadece bir döngü çalışıyor olmalı
        time.sleep(0.2)
        assert pm.is_cycle_running() is True

        # Temizlik
        pm.stop_current_cycle()

    def test_concurrent_start_and_stop(self, mock_coordinator):
        """Start ve stop aynı anda çağrılabilmeli."""
        pm = ProcessManager(mock_coordinator)
        errors = []

        def start_cycle():
            try:
                pm.start_new_cycle("https://t.me/ch/1")
            except Exception as e:
                errors.append(e)

        def stop_cycle():
            try:
                pm.stop_current_cycle()
            except Exception as e:
                errors.append(e)

        for _ in range(3):
            t1 = threading.Thread(target=start_cycle)
            t2 = threading.Thread(target=stop_cycle)
            t1.start()
            t2.start()
            t1.join(timeout=10)
            t2.join(timeout=10)

        assert len(errors) == 0

        # Temizlik
        pm.stop_current_cycle()
