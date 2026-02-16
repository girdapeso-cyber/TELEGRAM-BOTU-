"""Data models for KRBRZ Network Stress Tester.

ProxyInfo, EventInfo ve CycleState dataclass'ları.
Gereksinimler: 1.3 (event bilgisi kaydetme), 2.4 (tek döngü invariant'ı)
"""

import threading
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class ProxyInfo:
    """Proxy bilgisi.

    Attributes:
        address: Proxy adresi (ip:port formatında)
        proxy_type: Proxy tipi ('http', 'https', 'socks5')
    """

    address: str
    proxy_type: str  # 'http', 'https', 'socks5'

    def to_proxy_dict(self) -> Dict[str, str]:
        """requests kütüphanesi için proxy dict oluşturur.

        Returns:
            {'http': proxy_url, 'https': proxy_url} formatında dict.
            socks5 proxy'ler için 'socks5://' prefix'i eklenir.
        """
        if self.proxy_type == "socks5":
            proxy_url = f"socks5://{self.address}"
        else:
            proxy_url = f"http://{self.address}"
        return {"http": proxy_url, "https": proxy_url}


@dataclass
class EventInfo:
    """Telegram kanal event bilgisi.

    Gereksinim 1.3: Event'in mesaj ID'sini ve kanal bilgisini kaydetme.

    Attributes:
        channel: Telegram kanal adı
        message_id: Telegram mesaj ID'si
        url: Event'in tam URL'i
        timestamp: Event tespit zamanı (epoch)
    """

    channel: str
    message_id: str
    url: str
    timestamp: float


@dataclass
class CycleState:
    """Test döngüsü durumu.

    Gereksinim 2.4: Aynı anda yalnızca bir Event için Test_Cycle çalıştırma.

    Attributes:
        event_info: Döngünün ilişkili olduğu event bilgisi
        stop_event: Thread'ler arası durdurma sinyali
        thread_handle: Döngüyü çalıştıran ana thread
        is_running: Döngünün aktif olup olmadığı
    """

    event_info: EventInfo
    stop_event: threading.Event = field(default_factory=threading.Event)
    thread_handle: Optional[threading.Thread] = None
    is_running: bool = False
