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
        max_threads=int(os.getenv("MAX_THREADS", "1000")),
        proxy_api_base_url=os.getenv("PROXY_API_BASE_URL", "https://api.proxyscrape.com"),
        request_timeout=int(os.getenv("REQUEST_TIMEOUT", "2")),
        retry_delay=int(os.getenv("RETRY_DELAY", "5")),
        cycle_pause=int(os.getenv("CYCLE_PAUSE", "0")),
    )


def _parse_authorized_users(value: str) -> list[int]:
    """Parse comma-separated user IDs string into a list of integers."""
    if not value.strip():
        return []
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return [int(uid) for uid in parts]
