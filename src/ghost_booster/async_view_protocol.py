"""Async View Protocol for Ghost Booster.

Mevcut ViewProtocolHandler'ın aiohttp + aiohttp-socks tabanlı asenkron versiyonu.
Üç aşamalı Telegram view protokolünü uygular:
1. GET isteği ile sayfa alıp cookie çıkarma
2. POST isteği ile embed endpoint'inden data-view anahtarı alma
3. GET isteği ile görüntülenme kaydı

Gereksinimler:
    5.2: aiohttp + aiohttp-socks ile asenkron 3 adımlı protokol
    5.7: Yapılandırılabilir timeout
"""

from __future__ import annotations

import logging

import aiohttp
from aiohttp_socks import ProxyConnector

from src.models.proxy_models import ParsedProxy

logger = logging.getLogger(__name__)

# Ortak User-Agent havuzu — rotasyon ile fingerprint çeşitliliği
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
]
_ua_index = 0


def _next_ua() -> str:
    """Round-robin User-Agent döndürür."""
    global _ua_index
    ua = _USER_AGENTS[_ua_index % len(_USER_AGENTS)]
    _ua_index += 1
    return ua


class AsyncViewProtocol:
    """Telegram görüntülenme protokolünün asenkron versiyonu.

    aiohttp + aiohttp-socks kullanarak 3 adımlı view protokolünü
    asenkron olarak çalıştırır. Her proxy tipi (HTTP, SOCKS5) için
    ProxyConnector ile uygun bağlantı oluşturulur.

    Performans optimizasyonları:
    - DNS cache (ttl_dns_cache=300) ile tekrarlı DNS çözümlemesi önlenir
    - keep-alive bağlantıları (force_close=False) ile TCP handshake azaltılır
    - User-Agent rotasyonu ile fingerprint çeşitliliği sağlanır
    """

    def __init__(self, timeout: int = 10) -> None:
        """Protocol handler'ı başlatır.

        Args:
            timeout: Her HTTP isteği için timeout süresi (saniye).
        """
        self._timeout = timeout

    async def execute_view(
        self, channel: str, msg_id: str, proxy: ParsedProxy
    ) -> bool:
        """3 adımlı view protokolünü asenkron olarak çalıştırır.

        Sırasıyla: sayfa + cookie al → data-view anahtarı al → görüntülenme kaydet.
        Herhangi bir adım başarısız olursa False döner.

        Args:
            channel: Telegram kanal adı.
            msg_id: Telegram mesaj ID'si.
            proxy: ParsedProxy nesnesi.

        Returns:
            True: Tüm adımlar başarılı ise.
            False: Herhangi bir adım başarısız ise.
        """
        try:
            connector = ProxyConnector.from_url(
                proxy.to_url(),
                rdns=True,
                # DNS cache — aynı host'a tekrar çözümleme yapma
                ttl_dns_cache=300,
            )
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                # Otomatik header'lar — her istekte tekrar gönderilmez
                skip_auto_headers={"User-Agent"},
            ) as session:
                ua = _next_ua()
                cookie = await self._fetch_page_and_cookie(
                    session, channel, msg_id, ua
                )
                if cookie is None:
                    return False

                view_key = await self._fetch_view_key(
                    session, channel, msg_id, cookie, ua
                )
                if view_key is None:
                    return False

                return await self._register_view(
                    session, view_key, channel, msg_id, cookie, ua
                )
        except Exception:
            return False

    async def _fetch_page_and_cookie(
        self,
        session: aiohttp.ClientSession,
        channel: str,
        msg_id: str,
        ua: str,
    ) -> str | None:
        """Sayfayı GET isteği ile alır ve set-cookie header'ından cookie çıkarır.

        Args:
            session: aiohttp client session.
            channel: Telegram kanal adı.
            msg_id: Telegram mesaj ID'si.
            ua: User-Agent string'i.

        Returns:
            Cookie string'i veya hata durumunda None.
        """
        try:
            url = f"https://t.me/{channel}/{msg_id}"
            headers = {"User-Agent": ua}
            async with session.get(url, headers=headers) as response:
                cookie = response.headers.get("set-cookie", "").split(";")[0]
                if not cookie:
                    return None
                return cookie
        except Exception:
            return None

    async def _fetch_view_key(
        self,
        session: aiohttp.ClientSession,
        channel: str,
        msg_id: str,
        cookie: str,
        ua: str,
    ) -> str | None:
        """Embed endpoint'ine POST isteği gönderip data-view anahtarını çıkarır.

        Args:
            session: aiohttp client session.
            channel: Telegram kanal adı.
            msg_id: Telegram mesaj ID'si.
            cookie: Önceki adımdan alınan cookie string'i.
            ua: User-Agent string'i.

        Returns:
            data-view anahtarı veya hata durumunda None.
        """
        try:
            url = f"https://t.me/{channel}/{msg_id}?embed=1"
            headers = {
                "Accept": "*/*",
                "Connection": "keep-alive",
                "Content-type": "application/x-www-form-urlencoded",
                "Cookie": cookie,
                "Host": "t.me",
                "Origin": "https://t.me",
                "Referer": f"https://t.me/{channel}/{msg_id}?embed=1",
                "User-Agent": ua,
            }
            data = {"_rl": "1"}
            async with session.post(
                url, json=data, headers=headers
            ) as response:
                text = await response.text()
                if 'data-view="' not in text:
                    return None
                key = text.split('data-view="')[1].split('"')[0]
                return key if key else None
        except Exception:
            return None

    async def _register_view(
        self,
        session: aiohttp.ClientSession,
        view_key: str,
        channel: str,
        msg_id: str,
        cookie: str,
        ua: str,
    ) -> bool:
        """Görüntülenme endpoint'ine GET isteği göndererek görüntülenmeyi kaydeder.

        Args:
            session: aiohttp client session.
            view_key: data-view anahtarı.
            channel: Telegram kanal adı.
            msg_id: Telegram mesaj ID'si.
            cookie: Cookie string'i.
            ua: User-Agent string'i.

        Returns:
            True: İstek başarılı ise.
            False: Hata durumunda.
        """
        try:
            url = f"https://t.me/v/?views={view_key}"
            headers = {
                "Accept": "*/*",
                "Connection": "keep-alive",
                "Cookie": cookie,
                "Host": "t.me",
                "Referer": f"https://t.me/{channel}/{msg_id}?embed=1",
                "User-Agent": ua,
                "X-Requested-With": "XMLHttpRequest",
            }
            async with session.get(url, headers=headers) as response:
                await response.read()
            return True
        except Exception:
            return False
