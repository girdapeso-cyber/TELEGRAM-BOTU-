"""Emoji tepki motoru.

Postlara rastgele emoji tepkisi bırakan bileşen.
Ana bot'un API anahtarından bağımsız çalışır.
Gereksinimler: 6.1 (rastgele emoji), 6.2 (gecikme), 6.3 (Telethon), 6.7 (oturum yoksa devre dışı),
               6.8 (emoji listesi yapılandırma), 6.10 (flood wait)
"""

from __future__ import annotations

import asyncio
import logging
import random

from src.ghost_booster.session_manager import SessionManager

try:
    from telethon import TelegramClient
    from telethon.errors import FloodWaitError
    from telethon.tl.functions.messages import SendReactionRequest
    from telethon.tl.types import ReactionEmoji
except ImportError:  # pragma: no cover
    TelegramClient = None  # type: ignore[assignment,misc]
    FloodWaitError = None  # type: ignore[assignment,misc]
    SendReactionRequest = None  # type: ignore[assignment,misc]
    ReactionEmoji = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

DEFAULT_EMOJIS: list[str] = ["👏", "🔥", "❤️", "🎉", "👍"]
DEFAULT_COOLDOWN_SECONDS: float = 300.0


class ReactionEngine:
    """Postlara emoji tepkisi bırakan motor.

    SessionManager üzerinden Telethon oturumları ile çalışır.
    Yapılandırılmış emoji listesinden rastgele seçim yapar,
    insan benzeri gecikme uygular ve hata durumlarını yönetir.
    """

    def __init__(
        self,
        session_manager: SessionManager,
        emojis: list[str] | None = None,
        delay_min: float = 2.0,
        delay_max: float = 5.0,
    ) -> None:
        self._session_manager = session_manager
        self._emojis = emojis if emojis else DEFAULT_EMOJIS
        self._delay_min = delay_min
        self._delay_max = delay_max

    async def react_to_post(self, channel: str, msg_id: str) -> bool:
        """Bir posta rastgele emoji tepkisi bırakır.

        1. SessionManager'dan sonraki aktif oturumu al
        2. Rastgele emoji seç
        3. 2-5 saniye insan benzeri gecikme uygula
        4. Tepki gönder
        Başarısız olursa oturumu cooldown'a al.

        Returns:
            True başarılı, False başarısız.
        """
        session = await self._session_manager.get_next_session()
        if session is None:
            logger.warning("Aktif oturum yok, tepki gönderilemedi: %s/%s", channel, msg_id)
            return False

        client = self._session_manager.get_client(session)
        if client is None:
            logger.warning("Client bulunamadı: %s", session.session_path)
            await self._session_manager.mark_cooldown(session, DEFAULT_COOLDOWN_SECONDS)
            return False

        emoji = self.select_random_emoji()

        # İnsan benzeri gecikme
        delay = random.uniform(self._delay_min, self._delay_max)
        await asyncio.sleep(delay)

        try:
            await client(
                SendReactionRequest(
                    peer=channel,
                    msg_id=int(msg_id),
                    reaction=[ReactionEmoji(emoticon=emoji)],
                )
            )
            await self._session_manager.increment_reaction_count(session)
            logger.info(
                "Tepki gönderildi: %s → %s/%s (oturum: %s)",
                emoji,
                channel,
                msg_id,
                session.session_path,
            )
            return True

        except FloodWaitError as e:
            logger.warning(
                "Flood wait hatası: %s (%d saniye), oturum: %s",
                channel,
                e.seconds,
                session.session_path,
            )
            await self._session_manager.mark_cooldown(session, float(e.seconds))
            return False

        except Exception:
            logger.exception(
                "Tepki gönderimi başarısız: %s/%s, oturum: %s",
                channel,
                msg_id,
                session.session_path,
            )
            await self._session_manager.mark_cooldown(session, DEFAULT_COOLDOWN_SECONDS)
            return False

    def select_random_emoji(self) -> str:
        """Yapılandırılmış listeden rastgele emoji seçer."""
        return random.choice(self._emojis)

    def is_available(self) -> bool:
        """Tepki özelliğinin kullanılabilir olup olmadığını kontrol eder.

        En az bir aktif oturum varsa True döner.
        """
        return self._session_manager.has_active_sessions()
