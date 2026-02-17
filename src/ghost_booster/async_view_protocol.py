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


class AsyncViewProtocol:
    """Telegram görüntülenme protokolünün asenkron versiyonu.

    aiohttp + aiohttp-socks kullanarak 3 adımlı view protokolünü
    asenkron olarak çalıştırır. Her proxy tipi (HTTP, SOCKS5) için
    ProxyConnector ile uygun bağlantı oluşturulur.
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
            connector = ProxyConnector.from_url(proxy.to_url())
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            async with aiohttp.ClientSession(
                connector=connector, timeout=timeout
            ) as session:
                cookie = await self._fetch_page_and_cookie(
                    session, channel, msg_id
                )
                if cookie is None:
                    return False

                view_key = await self._fetch_view_key(
                    session, channel, msg_id, cookie
                )
                if view_key is None:
                    return False

                return await self._register_view(
                    session, view_key, channel, msg_id, cookie
                )
        except Exception:
            return False

    async def _fetch_page_and_cookie(
        self,
        session: aiohttp.ClientSession,
        channel: str,
        msg_id: str,
    ) -> str | None:
        """Sayfayı GET isteği ile alır ve set-cookie header'ından cookie çıkarır.

        Args:
            session: aiohttp client session.
            channel: Telegram kanal adı.
            msg_id: Telegram mesaj ID'si.

        Returns:
            Cookie string'i veya hata durumunda None.
        """
        try:
            url = f"https://t.me/{channel}/{msg_id}"
            async with session.get(url) as response:
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
    ) -> str | None:
        """Embed endpoint'ine POST isteği gönderip data-view anahtarını çıkarır.

        Args:
            session: aiohttp client session.
            channel: Telegram kanal adı.
            msg_id: Telegram mesaj ID'si.
            cookie: Önceki adımdan alınan cookie string'i.

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
                "User-Agent": "Chrome",
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
    ) -> bool:
        """Görüntülenme endpoint'ine GET isteği göndererek görüntülenmeyi kaydeder.

        Args:
            session: aiohttp client session.
            view_key: data-view anahtarı.
            channel: Telegram kanal adı.
            msg_id: Telegram mesaj ID'si.
            cookie: Cookie string'i.

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
                "User-Agent": "Chrome",
                "X-Requested-With": "XMLHttpRequest",
            }
            async with session.get(url, headers=headers) as response:
                await response.read()
            return True
        except Exception:
            return False
