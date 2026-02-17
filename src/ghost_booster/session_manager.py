"""Telegram oturum yönetimi.

.session dosyalarını yükler, round-robin dağılım, cooldown ve günlük limit yönetimi sağlar.
Gereksinimler: 6.4 (round-robin), 6.5 (cooldown), 6.6 (proxy atama), 6.9 (günlük limit), 6.10 (flood wait)
"""

from __future__ import annotations

import logging
import time
from datetime import date
from pathlib import Path

from src.models.proxy_models import ParsedProxy, SessionInfo

try:
    from telethon import TelegramClient
except ImportError:  # pragma: no cover
    TelegramClient = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


class SessionManager:
    """Telegram kullanıcı oturumlarını yöneten sınıf.

    .session dosyalarını dizinden yükler, round-robin ile dağıtır,
    cooldown ve günlük limit uygular, oturum başına proxy atar.
    """

    def __init__(
        self,
        session_dir: str,
        api_id: int,
        api_hash: str,
        daily_limit: int = 50,
    ) -> None:
        self._session_dir = session_dir
        self._api_id = api_id
        self._api_hash = api_hash
        self._daily_limit = daily_limit
        self._sessions: list[SessionInfo] = []
        self._clients: dict[str, TelegramClient] = {}  # type: ignore[type-arg]
        self._rr_index: int = 0

    async def initialize(self) -> None:
        """Session dizinindeki .session dosyalarını yükler ve client'ları başlatır."""
        session_path = Path(self._session_dir)
        if not session_path.exists():
            logger.warning("Session dizini bulunamadı: %s", self._session_dir)
            return

        session_files = sorted(session_path.glob("*.session"))
        if not session_files:
            logger.warning("Session dosyası bulunamadı: %s", self._session_dir)
            return

        for sf in session_files:
            session_name = str(sf.with_suffix(""))
            info = SessionInfo(
                session_path=session_name,
                daily_limit=self._daily_limit,
                last_reset_date=date.today().isoformat(),
            )
            self._sessions.append(info)

            if TelegramClient is not None:
                client = TelegramClient(session_name, self._api_id, self._api_hash)
                try:
                    await client.connect()
                    self._clients[session_name] = client
                    logger.info("Oturum bağlandı: %s", sf.name)
                except Exception:
                    logger.exception("Oturum bağlantısı başarısız: %s", sf.name)
                    info.is_active = False
            else:
                logger.warning(
                    "Telethon yüklü değil, client oluşturulamadı: %s", sf.name
                )

        logger.info(
            "Toplam %d oturum yüklendi (%d aktif)",
            len(self._sessions),
            sum(1 for s in self._sessions if s.is_active),
        )

    async def get_next_session(self) -> SessionInfo | None:
        """Round-robin ile sonraki aktif oturumu döner.

        Cooldown'daki ve günlük limite ulaşmış oturumları atlar.
        Gün değişmişse günlük sayacı sıfırlar.
        Tüm oturumlar kullanılamaz durumdaysa None döner.
        """
        if not self._sessions:
            return None

        today = date.today().isoformat()
        now = time.time()
        n = len(self._sessions)

        for _ in range(n):
            idx = self._rr_index % n
            self._rr_index = (self._rr_index + 1) % n
            session = self._sessions[idx]

            if not session.is_active:
                continue

            # Gün değişimi kontrolü — günlük sayacı sıfırla
            if session.last_reset_date != today:
                session.daily_reaction_count = 0
                session.last_reset_date = today

            # Cooldown kontrolü
            if session.cooldown_until > now:
                continue

            # Günlük limit kontrolü
            if session.daily_reaction_count >= session.daily_limit:
                continue

            return session

        return None

    async def mark_cooldown(self, session: SessionInfo, duration: float) -> None:
        """Oturumu belirtilen süre boyunca devre dışı bırakır."""
        session.cooldown_until = time.time() + duration
        logger.info(
            "Oturum cooldown'a alındı: %s (%.0f saniye)",
            session.session_path,
            duration,
        )

    async def increment_reaction_count(self, session: SessionInfo) -> None:
        """Oturumun günlük tepki sayacını artırır."""
        session.daily_reaction_count += 1
        if session.daily_reaction_count >= session.daily_limit:
            logger.info(
                "Oturum günlük limite ulaştı: %s (%d/%d)",
                session.session_path,
                session.daily_reaction_count,
                session.daily_limit,
            )

    async def assign_proxy(self, session: SessionInfo, proxy: ParsedProxy) -> None:
        """Oturuma proxy atar (IP rotasyonu)."""
        session.assigned_proxy = proxy.to_url()
        logger.debug(
            "Proxy atandı: %s → %s", session.session_path, session.assigned_proxy
        )

    def has_active_sessions(self) -> bool:
        """En az bir aktif oturum olup olmadığını kontrol eder."""
        now = time.time()
        today = date.today().isoformat()
        for session in self._sessions:
            if not session.is_active:
                continue
            # Gün değişimi — sayacı sıfırla
            if session.last_reset_date != today:
                session.daily_reaction_count = 0
                session.last_reset_date = today
            if session.cooldown_until > now:
                continue
            if session.daily_reaction_count >= session.daily_limit:
                continue
            return True
        return False

    async def close_all(self) -> None:
        """Tüm client bağlantılarını kapatır."""
        for path, client in self._clients.items():
            try:
                await client.disconnect()
                logger.info("Oturum kapatıldı: %s", path)
            except Exception:
                logger.exception("Oturum kapatma hatası: %s", path)
        self._clients.clear()
        self._sessions.clear()
        logger.info("Tüm oturumlar kapatıldı")

    def get_client(self, session: SessionInfo) -> TelegramClient | None:  # type: ignore[type-arg]
        """Oturuma ait Telethon client'ını döner."""
        return self._clients.get(session.session_path)
