"""Request Worker for KRBRZ Network Stress Tester.

Tek bir proxy üzerinden event URL'lerine istek gönderir.
URL'den kanal ve mesaj ID'sini parse eder, ViewProtocolHandler ile
görüntülenme protokolünü çalıştırır.

Gereksinimler:
    4.4: Her proxy için Telegram görüntülenme protokolünü uygulama
    4.5: Başarısız proxy isteğini sessizce yoksayıp sonraki proxy'ye geçme
    9.3: Event URL'i parse edilemezse o URL'i atlayıp devam etme
"""

import threading
from typing import List, Tuple

from src.services.view_protocol_handler import ViewProtocolHandler


class RequestWorker:
    """Tek bir proxy üzerinden event URL'lerine istek gönderen worker."""

    # Thread-safe global sayaç
    _view_count = 0
    _view_lock = threading.Lock()

    def __init__(
        self,
        proxy: str,
        event_urls: List[str],
        stop_event: threading.Event,
        view_handler: ViewProtocolHandler,
    ) -> None:
        self._proxy = proxy
        self._event_urls = event_urls
        self._stop_event = stop_event
        self._view_handler = view_handler

    def execute(self) -> None:
        """Tüm URL'ler için view protocol'ü çalıştırır."""
        for url in self._event_urls:
            if self._stop_event.is_set():
                return

            try:
                channel, msg_id = self.parse_url(url)
            except ValueError:
                continue

            try:
                success = self._view_handler.execute_view_protocol(
                    channel, msg_id, self._proxy
                )
                if success:
                    with RequestWorker._view_lock:
                        RequestWorker._view_count += 1
            except Exception:
                continue

    @classmethod
    def get_view_count(cls) -> int:
        """Toplam başarılı view sayısını döndürür."""
        with cls._view_lock:
            return cls._view_count

    @classmethod
    def reset_view_count(cls) -> None:
        """View sayacını sıfırlar."""
        with cls._view_lock:
            cls._view_count = 0

    @staticmethod
    def parse_url(url: str) -> Tuple[str, str]:
        """URL'den kanal ve mesaj ID'sini çıkarır.

        Beklenen format: https://t.me/{channel}/{msg_id}
        URL split('/') ile parçalanır: [3] = channel, [4] = msg_id

        Gereksinim 9.3: Geçersiz URL'lerde ValueError fırlatır.

        Args:
            url: Telegram post URL'i.

        Returns:
            (channel, msg_id) tuple'ı.

        Raises:
            ValueError: URL geçersiz formatta ise.
        """
        try:
            parts = url.split("/")
            channel = parts[3]
            msg_id = parts[4]
            if not channel or not msg_id:
                raise ValueError(f"Empty channel or msg_id in URL: {url}")
            return channel, msg_id
        except (IndexError, AttributeError):
            raise ValueError(f"Invalid URL format: {url}")
