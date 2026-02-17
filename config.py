"""Configuration loader for KRBRZ Network Stress Tester.

Loads configuration from environment variables with .env file support.
"""

import os

from dotenv import load_dotenv

from src.models.config import Configuration

# Load .env file if present
load_dotenv()


def load_configuration() -> Configuration:
    """Load configuration from environment variables.

    Environment Variables:
        TELEGRAM_BOT_TOKEN: (required) Telegram Bot API token
        AUTHORIZED_USERS: Comma-separated list of authorized user IDs
        TARGET_CHANNEL: Target Telegram channel username (without @)
        MAX_THREADS: Maximum concurrent threads (default: 400)
        PROXY_API_BASE_URL: Proxyscrape API base URL
        REQUEST_TIMEOUT: HTTP request timeout in seconds (default: 10)
        RETRY_DELAY: Retry delay in seconds (default: 5)
        CYCLE_PAUSE: Pause between cycles in seconds (default: 2)

    Returns:
        Configuration: Loaded configuration instance.

    Raises:
        ValueError: If required environment variables are missing.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")

    authorized_users_str = os.getenv("AUTHORIZED_USERS", "")
    authorized_users = _parse_authorized_users(authorized_users_str)

    return Configuration(
        telegram_bot_token=token,
        authorized_users=authorized_users,
        target_channel=os.getenv("TARGET_CHANNEL", "KRBZ_VIP_TR"),
        max_threads=int(os.getenv("MAX_THREADS", "400")),
        proxy_api_base_url=os.getenv("PROXY_API_BASE_URL", "https://api.proxyscrape.com"),
        request_timeout=int(os.getenv("REQUEST_TIMEOUT", "2")),
        retry_delay=int(os.getenv("RETRY_DELAY", "5")),
        cycle_pause=int(os.getenv("CYCLE_PAUSE", "0")),
        # Ghost Booster fields
        async_concurrency_limit=int(os.getenv("ASYNC_CONCURRENCY_LIMIT", "2000")),
        health_check_timeout=float(os.getenv("HEALTH_CHECK_TIMEOUT", "5.0")),
        health_check_concurrency=int(os.getenv("HEALTH_CHECK_CONCURRENCY", "500")),
        proxy_sources=_parse_proxy_sources(os.getenv("PROXY_SOURCES", "")),
        proxy_pool_critical_threshold=int(os.getenv("PROXY_POOL_CRITICAL_THRESHOLD", "10")),
        jitter_min_ms=int(os.getenv("JITTER_MIN_MS", "50")),
        jitter_max_ms=int(os.getenv("JITTER_MAX_MS", "200")),
        reaction_enabled=os.getenv("REACTION_ENABLED", "false").lower() in ("true", "1", "yes"),
        reaction_emojis=_parse_emojis(os.getenv("REACTION_EMOJIS", "👏,🔥,❤️,🎉,👍")),
        reaction_delay_min=float(os.getenv("REACTION_DELAY_MIN", "2.0")),
        reaction_delay_max=float(os.getenv("REACTION_DELAY_MAX", "5.0")),
        session_dir=os.getenv("SESSION_DIR", "sessions"),
        session_daily_limit=int(os.getenv("SESSION_DAILY_LIMIT", "50")),
        telegram_api_id=int(os.getenv("TELEGRAM_API_ID", "0")),
        telegram_api_hash=os.getenv("TELEGRAM_API_HASH", ""),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


def _parse_authorized_users(value: str) -> list[int]:
    """Parse comma-separated user IDs string into a list of integers."""
    if not value.strip():
        return []
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return [int(uid) for uid in parts]


def _parse_proxy_sources(value: str) -> list[str]:
    """Parse comma-separated proxy source URLs."""
    if not value.strip():
        return []
    return [s.strip() for s in value.split(",") if s.strip()]


def _parse_emojis(value: str) -> list[str]:
    """Parse comma-separated emoji list."""
    if not value.strip():
        return ["👏", "🔥", "❤️", "🎉", "👍"]
    return [e.strip() for e in value.split(",") if e.strip()]
