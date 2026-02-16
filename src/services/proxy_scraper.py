"""Proxy Scraper for KRBRZ Network Stress Tester.

Proxyscrape.com API'sinden HTTP, HTTPS ve SOCKS5 proxy listelerini çeker
ve dosyalara kaydeder.

Gereksinimler:
    3.1: Proxyscrape.com API'sinden HTTP, HTTPS ve SOCKS5 proxy'lerini çekme
    3.2: Proxy'leri proxies.txt ve socks.txt dosyalarına kaydetme
    3.3: Proxy çekme başarısız olursa 5 saniye bekleyip tekrar deneme
    9.2: Proxy_Pool çekme işlemi başarısız olursa hata toleransı
"""

import urllib.request
from typing import Tuple

import requests


class ProxyScraper:
    """Proxyscrape.com'dan proxy listelerini çeken ve dosyalara kaydeden sınıf.

    HTTP ve HTTPS proxy'leri birleştirilip proxies.txt'e,
    SOCKS5 proxy'leri socks.txt'e kaydedilir.

    Hata durumunda fetch_proxies() False döner ve çağıran taraf
    5 saniye bekleyip tekrar dener.
    """

    def __init__(self, api_base_url: str = "https://api.proxyscrape.com") -> None:
        """Proxy scraper'ı yapılandırır.

        Args:
            api_base_url: Proxyscrape API base URL'i.
        """
        self._api_base_url = api_base_url.rstrip("/")
        self._timeout = 5

    def fetch_proxies(self) -> bool:
        """Tüm proxy tiplerini çeker ve dosyalara kaydeder.

        HTTP, HTTPS ve SOCKS5 proxy'lerini Proxyscrape API'sinden çeker,
        ardından save_proxies() ile dosyalara yazar.

        Returns:
            True: Tüm proxy'ler başarıyla çekilip kaydedildiyse.
            False: Herhangi bir hata oluştuysa (çağıran taraf retry yapmalı).
        """
        try:
            http_https = self.fetch_http_https_proxies()
            socks5 = self.fetch_socks5_proxies()
            combined_http_https = http_https[0] + "\n" + http_https[1]
            self.save_proxies(combined_http_https, socks5)
            return True
        except Exception as e:
            print(f"Proxy çekme hatası: {e}")
            return False

    def fetch_http_https_proxies(self) -> Tuple[str, str]:
        """HTTP ve HTTPS proxy'lerini çeker.

        Returns:
            (https_proxies, http_proxies) tuple'ı olarak proxy listeleri.

        Raises:
            requests.RequestException: API isteği başarısız olursa.
        """
        system_proxies = urllib.request.getproxies()

        https_response = requests.get(
            f"{self._api_base_url}/?request=displayproxies&proxytype=https&timeout=0",
            proxies=system_proxies,
            timeout=self._timeout,
        )
        http_response = requests.get(
            f"{self._api_base_url}/?request=displayproxies&proxytype=http&timeout=0",
            proxies=system_proxies,
            timeout=self._timeout,
        )

        return (https_response.text, http_response.text)

    def fetch_socks5_proxies(self) -> str:
        """SOCKS5 proxy'lerini çeker.

        Returns:
            SOCKS5 proxy listesi (metin olarak).

        Raises:
            requests.RequestException: API isteği başarısız olursa.
        """
        system_proxies = urllib.request.getproxies()

        response = requests.get(
            f"{self._api_base_url}/?request=displayproxies&proxytype=socks5&timeout=0",
            proxies=system_proxies,
            timeout=self._timeout,
        )

        return response.text

    def save_proxies(self, http_https: str, socks5: str) -> None:
        """Proxy'leri dosyalara kaydeder.

        HTTP/HTTPS proxy'leri proxies.txt'e, SOCKS5 proxy'leri socks.txt'e yazılır.

        Args:
            http_https: Birleştirilmiş HTTP ve HTTPS proxy listesi.
            socks5: SOCKS5 proxy listesi.
        """
        with open("proxies.txt", "w", encoding="utf-8") as f:
            f.write(http_https)
        with open("socks.txt", "w", encoding="utf-8") as f:
            f.write(socks5)
