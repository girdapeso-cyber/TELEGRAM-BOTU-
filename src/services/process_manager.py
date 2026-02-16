"""Process Manager for KRBRZ Network Stress Tester.

Test döngülerini yönetir: eski işlemleri durdurur, yeni işlemleri başlatır.
Aynı anda yalnızca bir test döngüsü çalışmasını garanti eder.

Gereksinimler:
    2.1: Yeni event tespit edildiğinde devam eden tüm Test_Cycle işlemlerini derhal durdurma
    2.2: Stop_Signal gönderildiğinde tüm aktif Thread_Pool işlemlerini 5 saniye içinde sonlandırma
    2.3: Eski işlemler durdurulduktan sonra yeni event için Test_Cycle'ı gecikmesiz başlatma
    2.4: Aynı anda yalnızca bir Event için Test_Cycle çalıştırma
"""

import threading
import time
from typing import Optional

from src.models.data_models import CycleState, EventInfo
from src.services.stop_event_controller import StopEventController
from src.services.thread_coordinator import ThreadCoordinator
from src.services.request_worker import RequestWorker


class ProcessManager:
    """Test döngülerini yöneten sınıf.

    Orijinal tg.py'deki global auto_process_thread ve stop_event
    değişkenlerinin yerine geçer. Her yeni event geldiğinde eski
    döngüyü durdurur ve yeni döngüyü başlatır.

    Thread-safe: Tüm operasyonlar threading.Lock ile korunur.
    """

    JOIN_TIMEOUT = 5

    def __init__(self, thread_coordinator: ThreadCoordinator) -> None:
        """Process manager'ı başlatır.

        Args:
            thread_coordinator: Paralel test döngülerini koordine eden bileşen.
        """
        self._thread_coordinator = thread_coordinator
        self._stop_controller = StopEventController()
        self._lock = threading.Lock()
        self._current_cycle: Optional[CycleState] = None

    def start_new_cycle(self, event_url: str) -> None:
        """Yeni test döngüsü başlatır (tek URL). Eski döngü varsa önce durdurur.

        Args:
            event_url: Test edilecek event URL'i.
        """
        self.start_batch_cycle([event_url])

    def start_batch_cycle(self, event_urls: list) -> None:
        """Birden fazla URL için test döngüsü başlatır. Eski döngü varsa önce durdurur."""
        if not event_urls:
            return

        # Yeni batch başlıyor, sayacı sıfırla
        RequestWorker.reset_view_count()

        with self._lock:
            # Eski döngü varsa durdur
            if self._current_cycle is not None and self._current_cycle.is_running:
                self._stop_cycle_unlocked()

            # Yeni stop event oluştur
            stop_event = self._stop_controller.create_new_event()

            # İlk URL'den event bilgisi oluştur
            event_info = self._parse_event_info(event_urls[0])

            # Yeni CycleState oluştur
            cycle = CycleState(
                event_info=event_info,
                stop_event=stop_event,
                is_running=True,
            )

            # Thread başlat - tüm URL'leri geç
            thread = threading.Thread(
                target=self._run_cycle,
                args=(cycle, event_urls),
                daemon=True,
            )
            cycle.thread_handle = thread
            self._current_cycle = cycle
            thread.start()

    def stop_current_cycle(self) -> None:
        """Mevcut test döngüsünü durdurur.

        stop_event.set() ile sinyal gönderir ve thread'in
        bitmesini 5 saniye timeout ile bekler.

        Gereksinim 2.2: Stop_Signal gönderildiğinde 5 saniye içinde sonlandırma.
        """
        with self._lock:
            self._stop_cycle_unlocked()

    def is_cycle_running(self) -> bool:
        """Döngü durumunu kontrol eder.

        Returns:
            True: Aktif bir döngü çalışıyorsa.
            False: Döngü yoksa veya durmuşsa.
        """
        with self._lock:
            if self._current_cycle is None:
                return False
            # Thread hala yaşıyor mu kontrol et
            if (
                self._current_cycle.thread_handle is not None
                and self._current_cycle.thread_handle.is_alive()
            ):
                return True
            # Thread bitmiş ama is_running hala True ise güncelle
            self._current_cycle.is_running = False
            return False

    def _stop_cycle_unlocked(self) -> None:
        """Lock tutulurken mevcut döngüyü durdurur (internal).

        Bu metod lock dışından çağrılmamalıdır.
        """
        if self._current_cycle is None:
            return

        if not self._current_cycle.is_running:
            return

        # Stop sinyali gönder
        self._stop_controller.signal_stop()

        thread = self._current_cycle.thread_handle
        self._current_cycle.is_running = False

        if thread is not None and thread.is_alive():
            # Lock'u bırakıp join bekle (deadlock önleme)
            self._lock.release()
            try:
                thread.join(timeout=self.JOIN_TIMEOUT)
            finally:
                self._lock.acquire()

    def _run_cycle(self, cycle: CycleState, event_urls: list = None) -> None:
        """Thread içinde döngüyü çalıştırır.

        Args:
            cycle: Çalıştırılacak döngü durumu.
            event_urls: İşlenecek URL listesi (None ise cycle.event_info.url kullanılır).
        """
        try:
            urls = event_urls if event_urls else [cycle.event_info.url]
            self._thread_coordinator.run_continuous_cycle(
                event_urls=urls,
                stop_event=cycle.stop_event,
            )
        finally:
            cycle.is_running = False

    @staticmethod
    def _parse_event_info(event_url: str) -> EventInfo:
        """URL'den EventInfo oluşturur.

        Args:
            event_url: Telegram post URL'i (https://t.me/channel/msgid).

        Returns:
            Oluşturulan EventInfo nesnesi.
        """
        parts = event_url.rstrip("/").split("/")
        channel = parts[-2] if len(parts) >= 2 else ""
        message_id = parts[-1] if len(parts) >= 1 else ""

        return EventInfo(
            channel=channel,
            message_id=message_id,
            url=event_url,
            timestamp=time.time(),
        )
