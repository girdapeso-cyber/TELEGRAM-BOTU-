"""Ghost Booster proxy ve oturum veri modelleri.

ProxySource, ParsedProxy, HealthCheckResult, CycleReport ve SessionInfo dataclass'ları.
Gereksinimler: 2.6 (proxy nesnesi), 3.3 (sağlık kontrolü sonucu), 5.6 (döngü raporu), 6.4 (oturum bilgisi)
"""

from dataclasses import dataclass, field


@dataclass
class ProxySource:
    """Proxy kaynağı tanımı."""

    name: str
    url: str
    source_type: str  # "raw_list" | "proxyscrape_api" | "json_api"
    proxy_type: str  # "http" | "socks5" | "mixed"


@dataclass
class ParsedProxy:
    """Ayrıştırılmış ve normalize edilmiş proxy bilgisi."""

    protocol: str  # "http", "https", "socks5"
    host: str
    port: int
    username: str | None = None
    password: str | None = None

    def to_url(self) -> str:
        """Proxy'yi URL formatına dönüştürür (aiohttp-socks için)."""
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"

    def to_key(self) -> str:
        """Tekilleştirme anahtarı: host:port"""
        return f"{self.host}:{self.port}"


@dataclass
class HealthCheckResult:
    """Tek bir proxy'nin sağlık kontrolü sonucu."""

    proxy: ParsedProxy
    is_alive: bool
    response_time_ms: float
    main_page_ok: bool = False
    embed_page_ok: bool = False
    error: str | None = None


@dataclass
class CycleReport:
    """Bir View_Cycle'ın sonuç raporu."""

    total_proxies: int = 0
    successful_views: int = 0
    failed_views: int = 0
    views_per_url: dict[str, int] = field(default_factory=dict)
    avg_response_time_ms: float = 0.0


@dataclass
class SessionInfo:
    """Telegram kullanıcı oturumu bilgisi."""

    session_path: str
    is_active: bool = True
    cooldown_until: float = 0.0
    assigned_proxy: str | None = None
    daily_reaction_count: int = 0
    daily_limit: int = 50
    last_reset_date: str = ""
