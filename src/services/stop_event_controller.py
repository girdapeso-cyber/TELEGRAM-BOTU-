"""Stop Event Controller for KRBRZ Network Stress Tester.

Thread'ler arası stop sinyallerini yönetir. Yeni bir event geldiğinde
mevcut tüm işlemleri durdurmak için threading.Event nesneleri kullanır.

Gereksinimler:
    2.1: Yeni event tespit edildiğinde devam eden tüm Test_Cycle işlemlerini derhal durdurma
    2.2: Stop_Signal gönderildiğinde tüm aktif Thread_Pool işlemlerini sonlandırma
"""

import threading


class StopEventController:
    """Thread'ler arası stop sinyallerini yöneten controller.

    Her yeni test döngüsü için bir threading.Event oluşturur.
    signal_stop() çağrıldığında mevcut event set edilir ve
    tüm thread'ler is_stopped() kontrolü ile durur.

    Thread-safe: Tüm operasyonlar threading.Lock ile korunur.
    """

    def __init__(self) -> None:
        """Stop event controller'ı başlatır."""
        self._lock = threading.Lock()
        self._current_event: threading.Event | None = None

    def create_new_event(self) -> threading.Event:
        """Yeni stop event oluşturur.

        Mevcut event varsa önce onu set eder (eski thread'leri durdurur),
        sonra yeni bir event oluşturup döndürür.

        Returns:
            Yeni oluşturulan threading.Event nesnesi.
        """
        with self._lock:
            if self._current_event is not None:
                self._current_event.set()
            self._current_event = threading.Event()
            return self._current_event

    def signal_stop(self) -> None:
        """Mevcut event'e stop sinyali gönderir.

        Aktif bir event varsa set eder, yoksa sessizce geçer.
        Gereksinim 2.1: Devam eden tüm Test_Cycle işlemlerini derhal durdurma.
        """
        with self._lock:
            if self._current_event is not None:
                self._current_event.set()

    def is_stopped(self) -> bool:
        """Stop durumunu kontrol eder.

        Returns:
            True: Mevcut event set edilmişse veya hiç event yoksa.
            False: Mevcut event henüz set edilmemişse.
        """
        with self._lock:
            if self._current_event is None:
                return True
            return self._current_event.is_set()
