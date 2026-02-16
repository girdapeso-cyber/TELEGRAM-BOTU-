"""Command Handler - Kullanıcı komutlarını işler.

Telegram bot komutlarını yönetir ve yetkilendirme kontrolü yapar.
Gereksinimler: 6.1 (yetkilendirme), 6.2 (yetkisiz kullanıcı yoksayma), 7.1 (hoş geldin mesajı)
"""

from typing import List

from telegram import Update
from telegram.ext import ContextTypes


class BotCommandHandler:
    """Telegram bot komutlarını işleyen handler.

    Yalnızca yetkili kullanıcılardan gelen komutları işler.
    Yetkisiz kullanıcıların komutları sessizce yoksayılır.

    Attributes:
        authorized_users: Yetkili kullanıcı ID listesi.
        target_channel: İzlenen hedef kanal adı.
    """

    def __init__(self, authorized_users: List[int], target_channel: str):
        """Command handler'ı yapılandırır.

        Args:
            authorized_users: Yetkili kullanıcı Telegram ID listesi.
            target_channel: İzlenen Telegram kanal adı (@ olmadan).
        """
        self.authorized_users = authorized_users
        self.target_channel = target_channel

    def is_authorized(self, user_id: int) -> bool:
        """Kullanıcı yetkisini kontrol eder.

        Args:
            user_id: Kontrol edilecek Telegram kullanıcı ID'si.

        Returns:
            True eğer kullanıcı yetkili ise, False aksi halde.
        """
        return user_id in self.authorized_users

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/start komutunu işler.

        Yetkili kullanıcıya hoş geldin mesajı ve bot durum bilgisi gönderir.
        Yetkisiz kullanıcıların komutu sessizce yoksayılır.

        Args:
            update: Telegram Update nesnesi.
            context: Telegram bot context nesnesi.
        """
        user = update.effective_user
        if user is None or not self.is_authorized(user.id):
            return

        await update.message.reply_html(
            f"Merhaba {user.mention_html()}! 👋\n\n"
            f"Bot otomatik modda çalışıyor ve <b>@{self.target_channel}</b> kanalını dinliyor.\n"
            "Yeni gönderi olduğunda işlem başlayacaktır."
        )
