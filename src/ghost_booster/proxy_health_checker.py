"""Proxy sağlık kontrolü ve filtreleme modülü.

Proxy'leri Telegram sunucularına (hem t.me ana sayfa hem embed endpoint)
karşı test eder, ölüleri eler ve sağlıklıları yanıt süresine göre sıralar.

Gereksinimler: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8
"""

from __future__ import annotations

import asyncio
import logging
import time

import aiohttp
from aiohttp_socks import ProxyConnector

from src.models.proxy_models import HealthCheckResult, ParsedProxy

logger = logging.getLogger(__name__)

MAIN_PAGE_URL = "https://t.me"
EMBED_URL_TEMPLATE = "https://t.me/s/{channel}"


class ProxyHealthChecker:
    """Proxy'leri Telegram sunucularına karşı test eden ve sıralayan bileşen.

    Hem ``https://t.me`` ana sayfasını hem ``https://t.me/s/{channel}``
    embed endpoint'ini test eder. Her iki testi de geçen proxy'ler
    yanıt süresine göre artan sırada sıralanır.
    """

    def __init__(
        self,
        timeout: float = 5.0,
        concurrency: int = 500,
        target_channel: str = "",
    ) -> None:
        self._timeout = timeout
        self._concurrency = concurrency
        self._target_channel = target_channel

    async def check_all(self, proxies: list[ParsedProxy]) -> list[ParsedProxy]:
        """Tüm proxy'leri test eder, sağlıklıları yanıt süresine göre sıralayıp döner.

        Her iki endpoint'i de geçen proxy'ler dahil edilir.
        İstatistikleri loglar.

        Returns:
            Sıralı sağlıklı proxy listesi (en hızlı önce).
        """
        semaphore = asyncio.Semaphore(self._concurrency)

        async def _bounded_check(proxy: ParsedProxy) -> HealthCheckResult:
            async with semaphore:
                return await self._check_single(proxy)

        results: list[HealthCheckResult] = await asyncio.gather(
            *(_bounded_check(p) for p in proxies),
        )

        alive = [r for r in results if r.is_alive]
        alive.sort(key=lambda r: r.response_time_ms)

        # İstatistik loglama
        total = len(results)
        passed = len(alive)
        failed = total - passed
        avg_ms = sum(r.response_time_ms for r in alive) / passed if passed else 0.0

        logger.info(
            "Sağlık kontrolü tamamlandı: %d test edildi, %d geçti, %d elendi, "
            "ortalama yanıt süresi: %.1f ms",
            total,
            passed,
            failed,
            avg_ms,
        )

        return [r.proxy for r in alive]

    async def _check_single(self, proxy: ParsedProxy) -> HealthCheckResult:
        """Tek bir proxy'yi her iki endpoint'e karşı doğrular.

        1. ``https://t.me`` ana sayfasına bağlantı testi
        2. ``https://t.me/s/{channel}`` embed endpoint'ine bağlantı testi

        Her iki test de başarılıysa ``is_alive=True``.
        Toplam yanıt süresi milisaniye cinsinden kaydedilir.
        """
        start = time.perf_counter()
        main_page_ok = False
        embed_page_ok = False
        error: str | None = None

        try:
            connector = ProxyConnector.from_url(proxy.to_url())
            client_timeout = aiohttp.ClientTimeout(total=self._timeout)

            async with aiohttp.ClientSession(
                connector=connector,
                timeout=client_timeout,
            ) as session:
                # Test 1: Ana sayfa
                async with session.get(MAIN_PAGE_URL) as resp:
                    if resp.status == 200:
                        main_page_ok = True

                # Test 2: Embed endpoint
                embed_url = EMBED_URL_TEMPLATE.format(
                    channel=self._target_channel or "telegram",
                )
                async with session.get(embed_url) as resp:
                    if resp.status == 200:
                        embed_page_ok = True

        except Exception as exc:
            error = str(exc)

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        is_alive = main_page_ok and embed_page_ok

        return HealthCheckResult(
            proxy=proxy,
            is_alive=is_alive,
            response_time_ms=elapsed_ms,
            main_page_ok=main_page_ok,
            embed_page_ok=embed_page_ok,
            error=error,
        )
