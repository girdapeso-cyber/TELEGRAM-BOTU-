"""Bot Controller - Telegram Bot API ile iletişimi yönetir ve tüm bileşenleri wire eder.

Tüm bileşenleri dependency injection ile oluşturur, handler'ları kaydeder,
başlangıçta son N postu çeker ve bot polling'i başlatır.
"""

import requests
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from src.handlers.command_handler import BotCommandHandler
from src.handlers.event_handler import EventHandler
from src.models.config import Configuration
from src.services.notification_service import NotificationService
from src.services.process_manager import ProcessManager
from src.services.proxy_scraper import ProxyScraper
from src.services.thread_coordinator import ThreadCoordinator
from src.services.view_protocol_handler import ViewProtocolHandler


class BotController:
    """Telegram bot'unu yöneten ve tüm bileşenleri wire eden controller."""

    def __init__(self, config: Configuration) -> None:
        self.config = config

        # 1. Telegram Application build
        self.application = Application.builder().token(config.telegram_bot_token).build()

        # 2. Core servisler
        proxy_scraper = ProxyScraper(api_base_url=config.proxy_api_base_url)
        view_handler = ViewProtocolHandler(timeout=config.request_timeout)
        thread_coordinator = ThreadCoordinator(
            max_threads=config.max_threads,
            proxy_scraper=proxy_scraper,
            view_handler=view_handler,
            cycle_pause=config.cycle_pause,
        )
        self.process_manager = ProcessManager(thread_coordinator=thread_coordinator)

        # 3. NotificationService
        admin_id = config.authorized_users[0] if config.authorized_users else 0
        self.notification_service = NotificationService(
            bot=self.application.bot,
            admin_id=admin_id,
        )

        # 4. Handler'lar
        self.command_handler = BotCommandHandler(
            authorized_users=config.authorized_users,
            target_channel=config.target_channel,
        )
        self.event_handler = EventHandler(
            target_channel=config.target_channel,
            process_manager=self.process_manager,
            notification_service=self.notification_service,
            batch_size=config.batch_size,
        )

    def register_handlers(self) -> None:
        """Command ve message handler'ları kaydeder."""
        self.application.add_handler(
            CommandHandler("start", self.command_handler.handle_start)
        )
        self.application.add_handler(
            MessageHandler(
                filters.ChatType.CHANNEL,
                self.event_handler.handle_channel_post,
            )
        )

    async def _fetch_initial_posts(self) -> None:
        """Bot başlangıcında kanalın web sayfasından son batch_size postu çeker."""
        try:
            batch_size = self.config.batch_size
            channel = self.config.target_channel

            print(f"Kanaldan son {batch_size} post çekiliyor...")

            urls = self._scrape_recent_post_urls(channel, batch_size)

            if urls:
                print(f"{len(urls)} post bulundu, izleme başlatılıyor...")
                await self.event_handler.start_initial_batch(urls)
            else:
                print("Başlangıç postları bulunamadı, yeni post bekleniyor...")

        except Exception as e:
            print(f"Başlangıç postları çekilemedi: {e}")
            print("Yeni post bekleniyor...")

    def _scrape_recent_post_urls(self, channel: str, count: int) -> list:
        """Kanalın public web sayfasından son N post URL'ini scrape eder."""
        import re
        urls = []
        try:
            resp = requests.get(
                f"https://t.me/s/{channel}",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            if resp.status_code != 200:
                print(f"Kanal sayfası çekilemedi: HTTP {resp.status_code}")
                return urls

            # data-post="KRBZ_VIP_TR/123" formatındaki post ID'lerini bul
            pattern = rf'data-post="{re.escape(channel)}/(\d+)"'
            matches = re.findall(pattern, resp.text)

            if not matches:
                pattern2 = r'data-post="[^"]*?/(\d+)"'
                matches = re.findall(pattern2, resp.text)

            if matches:
                unique_ids = list(dict.fromkeys(matches))
                recent_ids = unique_ids[-count:]
                urls = [f"https://t.me/{channel}/{mid}" for mid in recent_ids]
                print(f"Bulunan post ID'leri: {recent_ids}")

        except Exception as e:
            print(f"Web scraping başarısız: {e}")

        return urls

    async def post_init(self, application) -> None:
        """Application başlatıldıktan sonra çalışır - ilk batch'i çeker."""
        await self._fetch_initial_posts()

    def start(self) -> None:
        """Bot'u çalıştırır ve polling başlatır."""
        self.register_handlers()
        # post_init callback'i ekle - polling başlamadan önce ilk batch çekilir
        self.application.post_init = self.post_init
        print(
            f"Bot çalışıyor ve @{self.config.target_channel} kanalını dinliyor..."
        )
        print(f"Batch boyutu: {self.config.batch_size} post")
        self.application.run_polling()
