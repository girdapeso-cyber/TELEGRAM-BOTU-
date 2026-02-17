"""Asyncio tabanlı worker havuzu.

Mevcut ThreadCoordinator'ın yerini alan, asyncio + aiohttp tabanlı
eşzamanlı bağlantı havuzu. Jitter ile rate limiting koruması sağlar.

Gereksinimler:
    5.1: asyncio.Semaphore ile eşzamanlılık kontrolü
    5.3: Her proxy için asenkron task oluşturma
    5.4: Başarısız proxy'yi sessizce atlama
    5.5: Yapılandırılabilir eşzamanlılık limiti
    5.6: Döngü raporu (CycleReport)
    5.8: Stop sinyali ile temiz kapatma
    5.9: Worker'lar arasına jitter ekleme
    5.10: Yapılandırılabilir jitter aralığı
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable

from src.ghost_booster.async_view_protocol import AsyncViewProtocol
from src.ghost_booster.proxy_pool import ProxyPool
from src.models.proxy_models import CycleReport, ParsedProxy

logger = logging.getLogger(__name__)


class AsyncWorkerPool:
    """Asyncio tabanlı worker havuzu.

    ProxyPool'dan proxy alarak her biri için asenkron view task'ları oluşturur.
    asyncio.Semaphore ile eşzamanlılık kontrolü ve jitter ile rate limiting
    koruması sağlar.
    """

    def __init__(
        self,
        concurrency_limit: int = 2000,
        request_timeout: int = 10,
        jitter_min_ms: int = 50,
        jitter_max_ms: int = 200,
    ) -> None:
        self._concurrency_limit = concurrency_limit
        self._request_timeout = request_timeout
        self._jitter_min_ms = jitter_min_ms
        self._jitter_max_ms = jitter_max_ms

    async def run_cycle(
        self,
        proxy_pool: ProxyPool,
        event_urls: list[str],
        stop_event: asyncio.Event,
        on_view_success: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> CycleReport:
        """Proxy havuzundan proxy alarak asenkron view task'ları çalıştırır.

        Her worker arasına jitter ekler. Stop sinyali alındığında aktif
        task'ları iptal edip temiz şekilde kapatır.

        Args:
            proxy_pool: Sağlıklı proxy'leri içeren havuz.
            event_urls: Telegram post URL'leri listesi.
            stop_event: Durdurma sinyali.
            on_view_success: View başarılı olduğunda çağrılacak callback.

        Returns:
            Döngü raporu.
        """
        report = CycleReport()
        view_protocol = AsyncViewProtocol(timeout=self._request_timeout)
        semaphore = asyncio.Semaphore(self._concurrency_limit)

        # Havuzdan tüm proxy'leri al
        proxies: list[ParsedProxy] = []
        while not proxy_pool.is_empty():
            proxy = proxy_pool.acquire()
            if proxy is not None:
                proxies.append(proxy)

        report.total_proxies = len(proxies)

        if not proxies or not event_urls:
            return report

        # Her proxy için worker task oluştur
        tasks: list[asyncio.Task[None]] = []
        for proxy in proxies:
            if stop_event.is_set():
                break
            task = asyncio.create_task(
                self._worker(
                    proxy=proxy,
                    event_urls=event_urls,
                    semaphore=semaphore,
                    stop_event=stop_event,
                    on_view_success=on_view_success,
                    report=report,
                    view_protocol=view_protocol,
                )
            )
            tasks.append(task)

        # Tüm task'ların tamamlanmasını bekle
        if tasks:
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.ALL_COMPLETED
            )
            # Stop sinyali geldiyse bekleyen task'ları iptal et
            if stop_event.is_set() and pending:
                for t in pending:
                    t.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

        logger.info(
            "Döngü tamamlandı: %d proxy, %d başarılı, %d başarısız",
            report.total_proxies,
            report.successful_views,
            report.failed_views,
        )

        return report

    async def _worker(
        self,
        proxy: ParsedProxy,
        event_urls: list[str],
        semaphore: asyncio.Semaphore,
        stop_event: asyncio.Event,
        on_view_success: Callable[[str, str], Awaitable[None]] | None,
        report: CycleReport,
        view_protocol: AsyncViewProtocol,
    ) -> None:
        """Tek bir proxy için tüm URL'lere view gönderir.

        Başarılı view'de on_view_success callback'ini çağırır.
        Her URL arasına jitter uygular. Stop sinyali geldiğinde erken çıkar.

        Args:
            proxy: Kullanılacak proxy.
            event_urls: Telegram post URL'leri.
            semaphore: Eşzamanlılık kontrolü için semaphore.
            stop_event: Durdurma sinyali.
            on_view_success: Başarı callback'i.
            report: Sonuçların yazılacağı rapor nesnesi.
            view_protocol: View protokolü handler'ı.
        """
        async with semaphore:
            for i, url in enumerate(event_urls):
                if stop_event.is_set():
                    return

                # İlk URL için jitter atla — hemen başla
                if i > 0:
                    jitter = random.uniform(
                        self._jitter_min_ms / 1000.0,
                        self._jitter_max_ms / 1000.0,
                    )
                    await asyncio.sleep(jitter)

                    if stop_event.is_set():
                        return

                # URL'den channel ve msg_id ayrıştır
                parts = url.rstrip("/").split("/")
                channel = parts[-2]
                msg_id = parts[-1]

                try:
                    start_time = time.monotonic()
                    success = await view_protocol.execute_view(
                        channel, msg_id, proxy
                    )
                    elapsed_ms = (time.monotonic() - start_time) * 1000

                    if success:
                        report.successful_views += 1
                        report.views_per_url[url] = (
                            report.views_per_url.get(url, 0) + 1
                        )
                        # Ortalama yanıt süresini güncelle
                        if report.avg_response_time_ms == 0.0:
                            report.avg_response_time_ms = elapsed_ms
                        else:
                            report.avg_response_time_ms = (
                                report.avg_response_time_ms + elapsed_ms
                            ) / 2.0

                        # Başarı callback'i çağır
                        if on_view_success is not None:
                            try:
                                await on_view_success(channel, msg_id)
                            except Exception:
                                logger.debug(
                                    "on_view_success callback hatası: %s/%s",
                                    channel,
                                    msg_id,
                                )
                    else:
                        report.failed_views += 1
                except Exception:
                    report.failed_views += 1
                    logger.debug(
                        "Worker hatası: proxy=%s url=%s",
                        proxy.to_key(),
                        url,
                    )
