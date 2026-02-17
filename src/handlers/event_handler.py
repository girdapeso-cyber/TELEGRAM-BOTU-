"""Event Handler - Kanal post'larını dinler ve kayan pencere mantığıyla işler.

Telegram kanalına gelen yeni post'ları tespit eder, hedef kanal filtrelemesi yapar.
Kayan pencere mantığı: Her zaman son N postu takip eder. Yeni post gelince en eski
post çıkar, yeni post girer. Döngü kesilmez, sadece URL listesi güncellenir.
"""

from typing import List

from telegram import Update
from telegram.ext import ContextTypes

from src.services.notification_service import NotificationService
from src.services.process_manager import ProcessManager


class EventHandler:
    """Telegram kanal post'larını kayan pencere mantığıyla işleyen handler.

    Attributes:
        target_channel: İzlenen hedef kanal adı (@ olmadan).
        process_manager: Test döngülerini yöneten bileşen.
        notification_service: Bildirim gönderen bileşen.
        batch_size: Aynı anda işlenecek post sayısı.
        _active_urls: Şu an işlenmekte olan URL'ler (kayan pencere).
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
        self._active_urls: List[str] = []

    async def handle_channel_post(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Yeni kanal post'unu işler - kayan pencere mantığıyla."""
        post = update.channel_post
        if post is None:
            return

        if post.chat.username != self.target_channel:
            return

        new_link = self.extract_post_url(post)

        # Kayan pencere: en eskiyi çıkar, yeniyi ekle
        if len(self._active_urls) >= self.batch_size:
            removed = self._active_urls.pop(0)
            removed_id = removed.rstrip("/").split("/")[-1]
            self.notification_service.log_console(
                f"Post #{removed_id} pencereden çıkarıldı"
            )

        self._active_urls.append(new_link)
        new_id = new_link.rstrip("/").split("/")[-1]
        self.notification_service.log_console(
            f"Yeni post eklendi → #{new_id} | Aktif pencere ({len(self._active_urls)}/{self.batch_size}):"
        )
        for url in self._active_urls:
            pid = url.rstrip("/").split("/")[-1]
            self.notification_service.log_console(f"  → #{pid}")

        # Döngü çalışıyorsa URL listesini canlı güncelle (döngü kesilmez)
        if self.process_manager.is_cycle_running():
            self.process_manager.update_urls(self._active_urls[:])
        else:
            # İlk kez başlat
            await self.notification_service.notify_new_batch(self._active_urls)
            self.process_manager.start_batch_cycle(self._active_urls[:])

    async def start_initial_batch(self, urls: List[str]) -> None:
        """Bot başlangıcında ilk batch'i başlatır."""
        if not urls:
            return

        self._active_urls = urls[: self.batch_size]
        self.notification_service.log_console(
            f"Başlangıç batch'i başlatılıyor ({len(self._active_urls)} post):"
        )
        for url in self._active_urls:
            pid = url.rstrip("/").split("/")[-1]
            self.notification_service.log_console(f"  → #{pid}")

        await self.notification_service.notify_new_batch(self._active_urls)
        self.process_manager.start_batch_cycle(self._active_urls[:])

    def extract_post_url(self, post) -> str:
        """Post'tan URL oluşturur."""
        return f"https://t.me/{post.chat.username}/{post.message_id}"
