"""Thread Coordinator for KRBRZ Network Stress Tester.

Thread havuzunu yönetir ve paralel test döngülerini koordine eder.
Her döngüde proxy'ler yenilenir, her proxy için bir worker thread
başlatılır ve tüm thread'ler tamamlanınca 2 saniye mola verilir.

Gereksinimler:
    3.4: Her Test_Cycle başlangıcında Proxy_Pool'u yenileme
    3.5: Proxy_Pool tükendiğinde yeni çekip döngüyü yeniden başlatma
    4.1: 400 eşzamanlı thread ile paralel işlem
    4.2: Proxy kullanılabilir olduğunda thread başlatma
    4.3: Aktif thread sayısı limiti aştığında bekleme
    8.2: Thread sayısı limite ulaştığında 0.1 saniye bekleme
    8.3: Test_Cycle tamamlandığında 2 saniye mola
    8.4: Kullanılmayan thread'leri düzgün sonlandırma
    10.1: Test_Cycle tamamlandığında yeni Proxy_Pool çekip döngüyü yeniden başlatma
    10.2: Stop_Signal gönderilmediği sürece Test_Cycle'ı sürekli tekrarlama
"""

import threading
import time
from threading import active_count
from typing import List

from src.services.proxy_scraper import ProxyScraper
from src.services.request_worker import RequestWorker
from src.services.view_protocol_handler import ViewProtocolHandler


class ThreadCoordinator:
    """Thread havuzunu yöneten ve paralel test döngülerini koordine eden sınıf.

    Ana döngü (run_continuous_cycle):
    1. Proxy'leri yenile (ProxyScraper)
    2. proxies.txt oku → her proxy için thread başlat
    3. socks.txt oku → her proxy için "socks5://" prefix ile thread başlat
    4. Tüm thread'lerin bitmesini bekle
    5. Stop event kontrolü
    6. 2 saniye mola
    7. Tekrarla
    """

    def __init__(
        self,
        max_threads: int,
        proxy_scraper: ProxyScraper,
        view_handler: ViewProtocolHandler,
        cycle_pause: int = 2,
    ) -> None:
        """Thread coordinator'ı yapılandırır.

        Args:
            max_threads: Maksimum eşzamanlı thread sayısı (Gereksinim 4.1).
            proxy_scraper: Proxy listelerini çeken scraper.
            view_handler: Görüntülenme protokolü handler'ı.
            cycle_pause: Döngü arası mola süresi (saniye, varsayılan 2).
        """
        self._max_threads = max_threads
        self._proxy_scraper = proxy_scraper
        self._view_handler = view_handler
        self._cycle_pause = cycle_pause
        self._shared_urls: List[str] = []
        self._urls_lock = threading.Lock()

    def update_urls(self, new_urls: List[str]) -> None:
        """Çalışan döngüyü durdurmadan URL listesini günceller."""
        with self._urls_lock:
            self._shared_urls = list(new_urls)
            ids = [u.rstrip("/").split("/")[-1] for u in new_urls]
            print(f"URL listesi güncellendi → aktif postlar: {ids}")

    def run_continuous_cycle(
        self, event_urls: List[str], stop_event: threading.Event
    ) -> None:
        """Sürekli test döngüsünü çalıştırır.

        Stop event set edilene kadar döngüyü tekrarlar:
        1. Proxy'leri yenile
        2. Worker thread'leri oluştur ve başlat
        3. Tüm thread'lerin bitmesini bekle
        4. 2 saniye mola

        Gereksinim 10.1: Döngü tamamlandığında yeni proxy çekip tekrarla.
        Gereksinim 10.2: Stop sinyali gelene kadar sürekli tekrarla.

        Args:
            event_urls: İşlenecek event URL'lerinin listesi.
            stop_event: Thread'ler arası durdurma sinyali.
        """
        # Başlangıç URL'lerini shared'a kopyala
        with self._urls_lock:
            self._shared_urls = list(event_urls)

        while not stop_event.is_set():
            # Her döngü başında güncel URL listesini al
            with self._urls_lock:
                current_urls = list(self._shared_urls)

            if not current_urls:
                time.sleep(1)
                continue

            if len(current_urls) > 1:
                ids = [u.rstrip("/").split("/")[-1] for u in current_urls]
                print(f"{len(current_urls)} post için yeni bir izlenme döngüsü başlıyor... {ids}")
            else:
                print(f"{current_urls[0]} için yeni bir izlenme döngüsü başlıyor...")

            # Gereksinim 3.4: Her döngü başında proxy yenileme
            if not self._proxy_scraper.fetch_proxies():
                print("Proxy'ler çekilemedi, 5 saniye bekleniyor.")
                time.sleep(5)
                continue

            if stop_event.is_set():
                break

            # Proxy dosyalarını oku ve proxy listesi oluştur
            proxies = self._read_proxy_files()

            if stop_event.is_set():
                break

            # Worker thread'leri oluştur ve başlat
            threads = self.spawn_worker_threads(proxies, current_urls, stop_event)

            # Tüm thread'lerin bitmesini bekle
            self.wait_all_threads(threads)

            if stop_event.is_set():
                if current_urls:
                    print(f"Batch işlemi durduruldu ({len(current_urls)} post).")
                break

            # Gereksinim 8.3: Döngü bitiminde 2 saniye mola
            views = RequestWorker.get_view_count()
            per_url = RequestWorker.get_view_count_per_url()
            print(f"Proxy listesi tamamlandı | Toplam başarılı view: {views}")
            min_views = 600
            low_posts = []
            for url, count in per_url.items():
                post_id = url.rstrip("/").split("/")[-1]
                status = "✓" if count >= min_views else "⚠ düşük"
                print(f"  → Post #{post_id}: {count} view {status}")
                if count < min_views:
                    low_posts.append(url)

            if low_posts and not stop_event.is_set():
                print(f"{len(low_posts)} post henüz {min_views} view'e ulaşmadı, devam ediliyor...")
                # Mola vermeden devam et
                continue

            print("Tüm postlar minimum view'e ulaştı. Kısa mola...")
            time.sleep(self._cycle_pause)

        print("Sürekli işlem döngüsü sonlandı.")

    def spawn_worker_threads(
        self,
        proxies: List[str],
        event_urls: List[str],
        stop_event: threading.Event,
    ) -> List[threading.Thread]:
        """Worker thread'leri oluşturur ve başlatır.

        Her proxy için:
        1. Stop event kontrolü
        2. Thread slot bekle (limit kontrolü)
        3. RequestWorker thread oluştur ve başlat

        Gereksinim 4.2: Her proxy için thread başlatma.

        Args:
            proxies: Proxy adresleri listesi.
            event_urls: İşlenecek event URL'leri.
            stop_event: Durdurma sinyali.

        Returns:
            Başlatılan thread'lerin listesi.
        """
        threads: List[threading.Thread] = []

        for proxy in proxies:
            if stop_event.is_set():
                break

            self.wait_for_thread_slot()

            if stop_event.is_set():
                break

            worker = RequestWorker(proxy, event_urls, stop_event, self._view_handler)
            thread = threading.Thread(target=worker.execute)
            threads.append(thread)
            thread.start()

        return threads

    def wait_for_thread_slot(self) -> None:
        """Thread limiti için bekler.

        Aktif thread sayısı max_threads'i aştığında 0.1 saniye uyuyup
        tekrar kontrol eder.

        Gereksinim 4.3: Aktif thread sayısı limiti aştığında bekleme.
        Gereksinim 8.2: 0.1 saniye bekleme aralığı.
        """
        while active_count() > self._max_threads:
            time.sleep(0.1)

    def wait_all_threads(self, threads: List[threading.Thread]) -> None:
        """Tüm thread'lerin bitmesini bekler.

        Gereksinim 8.4: Kullanılmayan thread'leri düzgün sonlandırma.

        Args:
            threads: Beklenecek thread listesi.
        """
        for thread in threads:
            thread.join()

    def _read_proxy_files(self) -> List[str]:
        """Proxy dosyalarını ve ekstra proxy'leri okur.

        proxies.txt'den HTTP/HTTPS, socks.txt'den SOCKS5,
        ve EXTRA_PROXIES env'den kullanıcı proxy'leri okunur.
        """
        import os
        proxies: List[str] = []

        try:
            with open("proxies.txt", "r", encoding="utf-8") as f:
                for line in f.readlines():
                    proxy = line.strip()
                    if proxy:
                        proxies.append(proxy)
        except FileNotFoundError:
            pass

        try:
            with open("socks.txt", "r", encoding="utf-8") as f:
                for line in f.readlines():
                    proxy = line.strip()
                    if proxy:
                        proxies.append("socks5://" + proxy)
        except FileNotFoundError:
            pass

        # Ekstra kullanıcı proxy'leri (user:pass@ip:port formatında)
        extra = os.getenv("EXTRA_PROXIES", "")
        if extra.strip():
            for line in extra.split(","):
                p = line.strip()
                if p:
                    if not p.startswith("http"):
                        p = "http://" + p
                    proxies.append(p)

        return proxies
