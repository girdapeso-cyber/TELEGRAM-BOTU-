"""Çoklu kaynaklı proxy toplama modülü.

Birden fazla kaynaktan (Proxyscrape API, GitHub repoları, özel URL'ler)
proxy toplar, ProxyFormatParser ile ayrıştırır, birleştirir ve tekilleştirir.

Gereksinimler: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8
"""

from __future__ import annotations

import logging

import aiohttp

from src.ghost_booster.proxy_format_parser import ProxyFormatParser
from src.models.proxy_models import ParsedProxy, ProxySource

logger = logging.getLogger(__name__)

# Varsayılan proxy kaynakları (ücretsiz, sıfır maliyet modeli)
DEFAULT_SOURCES: list[ProxySource] = [
    # Proxyscrape API - HTTP
    ProxySource(
        name="Proxyscrape HTTP",
        url="https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all",
        source_type="proxyscrape_api",
        proxy_type="http",
    ),
    # Proxyscrape API - SOCKS5
    ProxySource(
        name="Proxyscrape SOCKS5",
        url="https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=10000&country=all",
        source_type="proxyscrape_api",
        proxy_type="socks5",
    ),
    # TheSpeedX/PROXY-List - HTTP
    ProxySource(
        name="TheSpeedX HTTP",
        url="https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        source_type="raw_list",
        proxy_type="http",
    ),
    # TheSpeedX/PROXY-List - SOCKS5
    ProxySource(
        name="TheSpeedX SOCKS5",
        url="https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        source_type="raw_list",
        proxy_type="socks5",
    ),
    # clarketm/proxy-list - HTTP
    ProxySource(
        name="clarketm HTTP",
        url="https://raw.githubusercontent.com/clarketm/proxy-list/master/HTTP.txt",
        source_type="raw_list",
        proxy_type="http",
    ),
    # ShiftyTR/proxy-list
    ProxySource(
        name="ShiftyTR",
        url="https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/proxy.txt",
        source_type="raw_list",
        proxy_type="http",
    ),
]


class ProxyHunter:
    """Birden fazla kaynaktan proxy toplayan, birleştiren ve tekilleştiren bileşen.

    Mevcut ProxyScraper'ın yerini alır. Başarısız kaynakları atlayıp
    diğer kaynaklardan toplamaya devam eder.
    """

    def __init__(
        self,
        sources: list[ProxySource] | None = None,
        parser: ProxyFormatParser | None = None,
        timeout: int = 10,
    ) -> None:
        self._sources = sources if sources is not None else list(DEFAULT_SOURCES)
        self._parser = parser if parser is not None else ProxyFormatParser()
        self._timeout = timeout

    async def hunt_all(self) -> list[ParsedProxy]:
        """Tüm kaynaklardan proxy toplar, ayrıştırır, birleştirir, tekilleştirir.

        Başarısız kaynakları atlayıp devam eder.
        Kaynak bazlı istatistikleri loglar.

        Returns:
            Tekilleştirilmiş ParsedProxy listesi.
        """
        all_proxies: list[ParsedProxy] = []
        source_stats: dict[str, int] = {}

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self._timeout),
        ) as session:
            for source in self._sources:
                proxies = await self._fetch_from_source(source, session)
                source_stats[source.name] = len(proxies)
                all_proxies.extend(proxies)

        # Kaynak bazlı istatistik loglama
        for name, count in source_stats.items():
            logger.info("Kaynak: %s → %d proxy", name, count)

        # Tekilleştirme
        unique = self._deduplicate(all_proxies)

        logger.info(
            "Proxy toplama tamamlandı: %d toplam, %d tekilleştirilmiş (%d kaynak)",
            len(all_proxies),
            len(unique),
            len(self._sources),
        )

        return unique

    async def _fetch_from_source(
        self,
        source: ProxySource,
        session: aiohttp.ClientSession,
    ) -> list[ParsedProxy]:
        """Tek bir kaynaktan proxy çeker ve parser ile ayrıştırır.

        Hata durumunda boş liste döner (kaynak atlanır).
        """
        try:
            async with session.get(source.url) as response:
                if response.status != 200:
                    logger.warning(
                        "Kaynak başarısız: %s (HTTP %d)", source.name, response.status
                    )
                    return []

                raw_text = await response.text()

            proxies = self._parser.parse_many(raw_text)

            # Kaynak proxy_type bilgisini uygula (raw_list ip:port formatında
            # geldiğinde parser varsayılan olarak http atar; kaynak socks5 ise düzelt)
            if source.proxy_type != "mixed":
                for proxy in proxies:
                    # Sadece parser'ın varsayılan http atadığı durumda override et
                    if proxy.protocol == "http" and source.proxy_type != "http":
                        proxy.protocol = source.proxy_type

            logger.debug(
                "Kaynak: %s → %d proxy çekildi", source.name, len(proxies)
            )
            return proxies

        except aiohttp.ClientError as exc:
            logger.warning("Kaynak erişilemez: %s (%s)", source.name, exc)
            return []
        except TimeoutError:
            logger.warning("Kaynak zaman aşımı: %s", source.name)
            return []
        except Exception as exc:
            logger.warning("Kaynak hatası: %s (%s)", source.name, exc)
            return []

    def _deduplicate(self, proxies: list[ParsedProxy]) -> list[ParsedProxy]:
        """host:port bazında tekilleştirme yapar.

        İlk görülen proxy korunur, sonraki tekrarlar atılır.
        """
        seen: set[str] = set()
        unique: list[ParsedProxy] = []
        for proxy in proxies:
            key = proxy.to_key()
            if key not in seen:
                seen.add(key)
                unique.append(proxy)
        return unique
