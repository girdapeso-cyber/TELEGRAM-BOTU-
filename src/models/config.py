"""Configuration data model for KRBRZ Network Stress Tester."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Configuration:
    """Sistem yapılandırması.

    Tüm yapılandırma parametrelerini tek bir yerde tutar.
    Environment variable'lardan veya doğrudan değerlerden oluşturulabilir.

    Gereksinimler: 6.3 (token güvenliği), 6.4 (authorized users), 8.1 (yapılandırılabilir thread havuzu)
    """

    telegram_bot_token: str
    authorized_users: List[int] = field(default_factory=list)
    target_channel: str = "KRBZ_VIP_TR"
    max_threads: int = 400
    proxy_api_base_url: str = "https://api.proxyscrape.com"
    request_timeout: int = 10
    retry_delay: int = 5
    cycle_pause: int = 2
    batch_size: int = 4

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.telegram_bot_token:
            raise ValueError("telegram_bot_token is required")
        if self.max_threads < 1:
            raise ValueError("max_threads must be at least 1")
        if self.request_timeout < 1:
            raise ValueError("request_timeout must be at least 1")
        if self.retry_delay < 0:
            raise ValueError("retry_delay must be non-negative")
        if self.cycle_pause < 0:
            raise ValueError("cycle_pause must be non-negative")
        if self.batch_size < 1:
            raise ValueError("batch_size must be at least 1")
