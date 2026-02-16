"""Event Handler - Kanal post'larını dinler ve batch halinde işler.

Telegram kanalına gelen yeni post'ları tespit eder, hedef kanal filtrelemesi yapar.
Batch mantığı: Başlangıçta son N post alınır ve işlenir. Yeni postlar geldiğinde
biriktirilir, batch_size'a ulaşınca eski batch durdurulup yeni batch başlatılır.
"""

from typing import List

from telegram import Update
from telegram.ext import ContextTypes

from src.services.notification_service import NotificationService
from src.services.process_manager import ProcessManager


class EventHandler:
    """Telegram kanal post'larını batch halinde işleyen handler.

    Attributes:
        target_channel: İzlenen hedef kanal adı (@ olmadan).
        process_manager: Test döngülerini yöneten bileşen.
        notification_service: Bildirim gönderen bileşen.
        batch_size: Aynı anda işlenecek post sayısı.
        _pending_urls: Yeni gelen post URL'leri (batch dolana kadar biriktirilir).
        _active_urls: Şu an işlenmekte olan URL'ler.
    """

    def __init__(
        self,
        target_channel: str,
        process_manager: ProcessManager,
        notification_service: NotificationService,
        batch_size: int = 4,
    ) -> None:
        self.target_channel = target_channel
        self.process_manager = process_manager
        self.notification_service = notification_service
        self.batch_size = batch_size
        self._pending_urls: List[str] = []
        self._active_urls: List[str] = []

    async def handle_channel_post(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Yeni kanal post'unu işler - batch mantığıyla."""
        post = update.channel_post
        if post is None:
            return

        if post.chat.username != self.target_channel:
            return

        new_link = self.extract_post_url(post)
        self._pending_urls.append(new_link)
        self.notification_service.log_console(
            f"Yeni post eklendi (bekleyen: {len(self._pending_urls)}/{self.batch_size}): {new_link}"
        )

        # Batch doldu mu kontrol et
        if len(self._pending_urls) >= self.batch_size:
            await self._switch_to_new_batch()

    async def _switch_to_new_batch(self) -> None:
        """Bekleyen URL'lerden yeni batch oluşturur ve döngüyü değiştirir."""
        # Eski döngüyü durdur
        if self.process_manager.is_cycle_running():
            self.notification_service.log_console(
                "Önceki batch işlemi durduruluyor..."
            )
            await self.notification_service.notify_cycle_stopped()
            self.process_manager.stop_current_cycle()

        # Yeni batch'i al
        self._active_urls = self._pending_urls[: self.batch_size]
        self._pending_urls = self._pending_urls[self.batch_size :]

        self.notification_service.log_console(
            f"Yeni batch başlatılıyor ({len(self._active_urls)} post):"
        )
        for url in self._active_urls:
            self.notification_service.log_console(f"  → {url}")

        # Bildirim gönder
        await self.notification_service.notify_new_batch(self._active_urls)

        # Yeni döngüyü başlat
        self.process_manager.start_batch_cycle(self._active_urls)

    async def start_initial_batch(self, urls: List[str]) -> None:
        """Bot başlangıcında ilk batch'i başlatır.

        Args:
            urls: Kanaldan alınan son N post URL'i.
        """
        if not urls:
            return

        self._active_urls = urls[: self.batch_size]
        self.notification_service.log_console(
            f"Başlangıç batch'i başlatılıyor ({len(self._active_urls)} post):"
        )
        for url in self._active_urls:
            self.notification_service.log_console(f"  → {url}")

        await self.notification_service.notify_new_batch(self._active_urls)
        self.process_manager.start_batch_cycle(self._active_urls)

    def extract_post_url(self, post) -> str:
        """Post'tan URL oluşturur."""
        return f"https://t.me/{post.chat.username}/{post.message_id}"
