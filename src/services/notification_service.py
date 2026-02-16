"""Notification Service - Kullanıcılara ve konsola bildirim gönderir.

Telegram Bot API üzerinden admin kullanıcıya bildirim gönderir
ve konsola işlem durumu logları yazar.
"""


class NotificationService:
    """Telegram bot bildirimleri ve konsol logging servisi.

    Attributes:
        bot: Telegram Bot instance (send_message desteği olan).
        admin_id: Bildirimlerin gönderileceği admin kullanıcı ID'si.
    """

    def __init__(self, bot, admin_id: int):
        """Notification service'i yapılandırır.

        Args:
            bot: Telegram Bot instance.
            admin_id: Admin kullanıcı Telegram ID'si.
        """
        self.bot = bot
        self.admin_id = admin_id

    async def notify_new_event(self, event_url: str) -> None:
        """Yeni event bildirimi gönderir.

        Args:
            event_url: Yeni event'in URL'i.
        """
        message = f"Yeni gönderi için izlenme işlemi başlatılıyor:\n{event_url}"
        try:
            await self.bot.send_message(self.admin_id, message)
        except Exception:
            self.log_console(f"Bildirim gönderilemedi: notify_new_event({event_url})")

    async def notify_new_batch(self, event_urls: list) -> None:
        """Yeni batch bildirimi gönderir.

        Args:
            event_urls: Batch'teki URL'lerin listesi.
        """
        urls_text = "\n".join(event_urls)
        message = f"Yeni batch başlatılıyor ({len(event_urls)} post):\n{urls_text}"
        try:
            await self.bot.send_message(self.admin_id, message)
        except Exception:
            self.log_console(f"Bildirim gönderilemedi: notify_new_batch")

    async def notify_cycle_stopped(self) -> None:
        """Döngü durdurma bildirimi gönderir.

        Admin kullanıcıya yeni gönderi algılandığını ve önceki
        işlemin durdurulduğunu bildirir.
        """
        message = "Yeni gönderi algılandı. Önceki işlem durduruluyor..."
        try:
            await self.bot.send_message(self.admin_id, message)
        except Exception:
            self.log_console("Bildirim gönderilemedi: notify_cycle_stopped")

    def log_console(self, message: str) -> None:
        """Konsola log yazar.

        Args:
            message: Konsola yazılacak log mesajı.
        """
        print(message)
