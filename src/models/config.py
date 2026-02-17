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

    # --- Ghost Booster alanları ---
    async_concurrency_limit: int = 300
    health_check_timeout: float = 3.0
    health_check_concurrency: int = 100
    proxy_sources: list[str] = field(default_factory=list)
    proxy_pool_critical_threshold: int = 20
    jitter_min_ms: int = 10
    jitter_max_ms: int = 50
    reaction_enabled: bool = False
    reaction_emojis: list[str] = field(default_factory=lambda: ["👏", "🔥", "❤️", "🎉", "👍"])
    reaction_delay_min: float = 2.0
    reaction_delay_max: float = 5.0
    session_dir: str = "sessions"
    session_daily_limit: int = 50
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    log_level: str = "INFO"

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

        # Ghost Booster doğrulamaları
        if self.async_concurrency_limit < 1:
            raise ValueError("async_concurrency_limit must be at least 1")
        if self.health_check_timeout <= 0:
            raise ValueError("health_check_timeout must be greater than 0")
        if self.health_check_concurrency < 1:
            raise ValueError("health_check_concurrency must be at least 1")
        if self.proxy_pool_critical_threshold < 0:
            raise ValueError("proxy_pool_critical_threshold must be non-negative")
        if self.jitter_min_ms < 0:
            raise ValueError("jitter_min_ms must be non-negative")
        if self.jitter_max_ms < self.jitter_min_ms:
            raise ValueError("jitter_max_ms must be >= jitter_min_ms")
        if self.reaction_delay_min < 0:
            raise ValueError("reaction_delay_min must be non-negative")
        if self.reaction_delay_max < self.reaction_delay_min:
            raise ValueError("reaction_delay_max must be >= reaction_delay_min")
        if self.session_daily_limit < 1:
            raise ValueError("session_daily_limit must be at least 1")
