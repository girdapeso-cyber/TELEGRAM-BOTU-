"""View Protocol Handler for KRBRZ Network Stress Tester.

Telegram görüntülenme protokolünü uygular. Üç aşamalı protokol:
1. GET isteği ile sayfa alıp cookie çıkarma
2. POST isteği ile embed endpoint'inden data-view anahtarı alma
3. GET isteği ile görüntülenme kaydı

Gereksinimler:
    5.1: Sayfayı GET isteği ile alma
    5.2: Cookie bilgisini çıkarma
    5.3: Embed endpoint'ine POST isteği ile data-view anahtarı alma
    5.4: Görüntülenme endpoint'ine GET isteği ile görüntülenme kaydı
    5.5: Her adımda 10 saniye timeout
    9.1: Timeout hatalarını sessizce işleme
    9.5: Tüm network hatalarını yakalayıp sessizce işleme
"""

from typing import Optional

import requests


class ViewProtocolHandler:
    """Telegram görüntülenme protokolünü uygulayan handler.

    Üç aşamalı protokolü sırayla çalıştırır. Her adımda timeout uygulanır
    ve tüm hatalar sessizce yakalanır (hata toleransı).
    """

    def __init__(self, timeout: int = 10) -> None:
        """Protocol handler'ı başlatır.

        Args:
            timeout: Her HTTP isteği için timeout süresi (saniye).
        """
        self._timeout = timeout

    def execute_view_protocol(
        self, channel: str, msg_id: str, proxy: str
    ) -> bool:
        """Tam görüntülenme protokolünü çalıştırır.

        Sırasıyla: sayfa + cookie al → data-view anahtarı al → görüntülenme kaydet.
        Herhangi bir adım başarısız olursa False döner.

        Args:
            channel: Telegram kanal adı.
            msg_id: Telegram mesaj ID'si.
            proxy: Proxy adresi (ör. "http://1.2.3.4:8080" veya "socks5://1.2.3.4:1080").

        Returns:
            True: Tüm adımlar başarılı ise.
            False: Herhangi bir adım başarısız ise.
        """
        try:
            proxy_dict = {"http": proxy, "https": proxy}
            session = requests.Session()

            cookie = self.fetch_page_and_cookie(
                channel, msg_id, proxy_dict, session
            )
            if cookie is None:
                return False

            view_key = self.fetch_view_key(
                channel, msg_id, cookie, proxy_dict, session
            )
            if view_key is None:
                return False

            return self.register_view(
                view_key, channel, msg_id, cookie, proxy_dict, session
            )
        except Exception:
            return False

    def fetch_page_and_cookie(
        self,
        channel: str,
        msg_id: str,
        proxy_dict: dict,
        session: requests.Session,
    ) -> Optional[str]:
        """Sayfayı GET isteği ile alır ve set-cookie header'ından cookie çıkarır.

        Gereksinim 5.1: Sayfayı GET isteği ile alma.
        Gereksinim 5.2: Cookie bilgisini çıkarma.

        Args:
            channel: Telegram kanal adı.
            msg_id: Telegram mesaj ID'si.
            proxy_dict: requests proxy dict'i.
            session: HTTP session nesnesi.

        Returns:
            Cookie string'i veya hata durumunda None.
        """
        try:
            url = f"https://t.me/{channel}/{msg_id}"
            response = session.get(
                url, timeout=self._timeout, proxies=proxy_dict
            )
            cookie = response.headers.get("set-cookie", "").split(";")[0]
            if not cookie:
                return None
            return cookie
        except Exception:
            return None

    def fetch_view_key(
        self,
        channel: str,
        msg_id: str,
        cookie: str,
        proxy_dict: dict,
        session: requests.Session,
    ) -> Optional[str]:
        """Embed endpoint'ine POST isteği gönderip data-view anahtarını çıkarır.

        Gereksinim 5.3: Embed endpoint'ine POST isteği ile data-view anahtarı alma.

        Args:
            channel: Telegram kanal adı.
            msg_id: Telegram mesaj ID'si.
            cookie: Önceki adımdan alınan cookie string'i.
            proxy_dict: requests proxy dict'i.
            session: HTTP session nesnesi.

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
            response = session.post(
                url,
                json=data,
                headers=headers,
                proxies=proxy_dict,
                timeout=self._timeout,
            )
            if 'data-view="' not in response.text:
                return None
            key = response.text.split('data-view="')[1].split('"')[0]
            return key if key else None
        except Exception:
            return None

    def register_view(
        self,
        view_key: str,
        channel: str,
        msg_id: str,
        cookie: str,
        proxy_dict: dict,
        session: requests.Session,
    ) -> bool:
        """Görüntülenme endpoint'ine GET isteği göndererek görüntülenmeyi kaydeder.

        Gereksinim 5.4: Görüntülenme endpoint'ine GET isteği ile kayıt.

        Args:
            view_key: data-view anahtarı.
            channel: Telegram kanal adı.
            msg_id: Telegram mesaj ID'si.
            cookie: Cookie string'i.
            proxy_dict: requests proxy dict'i.
            session: HTTP session nesnesi.

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
            session.get(
                url,
                headers=headers,
                proxies=proxy_dict,
                timeout=self._timeout,
            )
            return True
        except Exception:
            return False
