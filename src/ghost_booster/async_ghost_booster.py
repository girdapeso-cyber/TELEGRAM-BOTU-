"""AsyncGhostBooster — Ana orkestratör.

Tüm Ghost Booster bileşenlerini orkestre eder:
ProxyHunter → ProxyHealthChecker → ProxyPool → AsyncWorkerPool → ReactionEngine

Sürekli boost döngüsü çalıştırır, proxy havuzunu otomatik yeniler,
stop sinyali ile temiz kapatma sağlar.

Gereksinimler: 4.1, 4.3, 4.5, 8.1, 8.2, 8.5, 9.1, 9.2, 9.3, 9.4, 9.5
"""

from __future__ import annotations

import asyncio
import logging

from src.ghost_booster.async_worker_pool import AsyncWorkerPool
from src.ghost_booster.proxy_health_checker import ProxyHealthChecker
from src.ghost_booster.proxy_hunter import ProxyHunter
from src.ghost_booster.proxy_pool import ProxyPool
from src.ghost_booster.reaction_engine import ReactionEngine
from src.ghost_booster.session_manager import SessionManager
from src.models.config import Configuration
from src.models.proxy_models import ProxySource

logger = logging.getLogger(__name__)

RESTART_DELAY_SECONDS = 10


class AsyncGhostBooster:
    """Tüm Ghost Booster bileşenlerini orkestre eden ana sınıf.

    Configuration'dan tüm alt bileşenleri oluşturur ve sürekli
    boost döngüsünü yönetir.
    """

    def __init__(self, config: Configuration) -> None:
        self._config = config
        self._refill_lock = asyncio.Lock()
        self._refill_task: asyncio.Task[None] | None = None

        # Loglama seviyesini yapılandır
        logging.getLogger("src.ghost_booster").setLevel(
            getattr(logging, config.log_level.upper(), logging.INFO)
        )

        # Proxy kaynakları: config.proxy_sources URL listesini ProxySource nesnelerine dönüştür
        custom_sources: list[ProxySource] | None = None
        if config.proxy_sources:
            custom_sources = [
                ProxySource(
                    name=f"Custom-{i}",
                    url=url.strip(),
                    source_type="raw_list",
                    proxy_type="http",
                )
                for i, url in enumerate(config.proxy_sources)
                if url.strip()
            ]

        # Alt bileşenler
        self._hunter = ProxyHunter(
            sources=custom_sources,
            timeout=config.request_timeout,
        )
        self._checker = ProxyHealthChecker(
            timeout=config.health_check_timeout,
            concurrency=config.health_check_concurrency,
            target_channel=config.target_channel,
        )
        self._pool = ProxyPool(
            critical_threshold=config.proxy_pool_critical_threshold,
        )
        self._worker_pool = AsyncWorkerPool(
            concurrency_limit=config.async_concurrency_limit,
            request_timeout=config.request_timeout,
            jitter_min_ms=config.jitter_min_ms,
            jitter_max_ms=config.jitter_max_ms,
        )

        # Reaction bileşenleri (opsiyonel)
        self._reaction_enabled = config.reaction_enabled
        self._session_manager: SessionManager | None = None
        self._reaction_engine: ReactionEngine | None = None

        if self._reaction_enabled:
            self._session_manager = SessionManager(
                session_dir=config.session_dir,
                api_id=config.telegram_api_id,
                api_hash=config.telegram_api_hash,
                daily_limit=config.session_daily_limit,
            )
            self._reaction_engine = ReactionEngine(
                session_manager=self._session_manager,
                emojis=config.reaction_emojis,
                delay_min=config.reaction_delay_min,
                delay_max=config.reaction_delay_max,
            )

    async def run_continuous(
        self,
        event_urls: list[str],
        stop_event: asyncio.Event,
    ) -> None:
        """Sürekli boost döngüsünü çalıştırır.

        1. ProxyHunter ile proxy topla
        2. ProxyFormatParser ile normalize et (hunt_all içinde)
        3. ProxyHealthChecker ile filtrele ve sırala
        4. ProxyPool'a yükle
        5. AsyncWorkerPool ile view gönder (jitter ile)
        6. ReactionEngine ile tepki bırak (opsiyonel, callback ile)
        7. Pool kritik eşiğe düşünce veya tükenince 1'e dön

        Yakalanmamış istisna → logla, 10 saniye bekle, yeniden başlat (Req 8.5).
        Stop sinyali → temiz kapatma.
        """
        logger.info("AsyncGhostBooster başlatılıyor — %d URL", len(event_urls))

        # SessionManager'ı başlat (reaction etkinse)
        if self._session_manager is not None:
            await self._session_manager.initialize()

        try:
            while not stop_event.is_set():
                try:
                    await self._run_loop(event_urls, stop_event)
                except Exception:
                    if stop_event.is_set():
                        break
                    # Req 8.5: yakalanmamış istisna → logla, 10s bekle, yeniden başlat
                    logger.exception(
                        "Beklenmeyen hata, %d saniye sonra yeniden başlatılacak",
                        RESTART_DELAY_SECONDS,
                    )
                    try:
                        await asyncio.wait_for(
                            stop_event.wait(),
                            timeout=RESTART_DELAY_SECONDS,
                        )
                    except TimeoutError:
                        pass
        finally:
            # Temiz kapatma
            await self._shutdown()

    async def _run_loop(
        self,
        event_urls: list[str],
        stop_event: asyncio.Event,
    ) -> None:
        """Tek bir boost döngüsü: refill → cycle → tekrar."""
        # İlk dolum
        await self._refill_pool()

        while not stop_event.is_set():
            # Havuz tamamen boş → senkron refill (bekle)
            if self._pool.is_empty():
                logger.info(
                    "Proxy havuzu boş, yeniden dolduruluyor..."
                )
                await self._refill_pool()
            elif self._pool.is_critical():
                # Kritik ama boş değil → arka planda refill başlat, döngüye devam et
                if self._refill_task is None or self._refill_task.done():
                    logger.info(
                        "Proxy havuzu kritik (kalan: %d), arka planda dolduruluyor...",
                        self._pool.size(),
                    )
                    self._refill_task = asyncio.create_task(self._refill_pool())

            # Hâlâ boşsa tüm kaynaklar başarısız demektir → retry_delay bekle (Req 8.2)
            if self._pool.is_empty():
                logger.warning(
                    "Tüm kaynaklar başarısız, %d saniye bekleniyor...",
                    self._config.retry_delay,
                )
                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=self._config.retry_delay,
                    )
                except TimeoutError:
                    pass
                continue

            # Worker cycle çalıştır
            report = await self._worker_pool.run_cycle(
                proxy_pool=self._pool,
                event_urls=event_urls,
                stop_event=stop_event,
                on_view_success=self._on_view_success if self._reaction_enabled else None,
            )

            # Req 9.1: döngü raporu logla
            logger.info(
                "Döngü raporu: %d proxy, %d başarılı view, %d başarısız, "
                "ortalama yanıt: %.1f ms",
                report.total_proxies,
                report.successful_views,
                report.failed_views,
                report.avg_response_time_ms,
            )

    async def _on_view_success(self, channel: str, msg_id: str) -> None:
        """View başarılı olduğunda çağrılan callback — tepki motorunu tetikler."""
        if (
            self._reaction_engine is not None
            and self._reaction_engine.is_available()
        ):
            await self._reaction_engine.react_to_post(channel, msg_id)

    async def _refill_pool(self) -> None:
        """Proxy havuzunu yeniden doldurur (hunt → check → load).

        Lock ile eşzamanlı refill'i önler.
        Req 9.2: kaynak bazlı istatistikler (hunter içinde loglanır)
        Req 9.3: sağlık kontrolü istatistikleri (checker içinde loglanır)
        """
        async with self._refill_lock:
            logger.info("Proxy havuzu yeniden dolduruluyor...")

            # 1. Proxy topla
            raw_proxies = await self._hunter.hunt_all()
            if not raw_proxies:
                logger.warning("Hiç proxy toplanamadı")
                return

            # 2. Sağlık kontrolü
            healthy_proxies = await self._checker.check_all(raw_proxies)
            if not healthy_proxies:
                logger.warning("Sağlık kontrolünden geçen proxy yok")
                return

            # 3. Havuza yükle
            self._pool.load(healthy_proxies)
            logger.info(
                "Havuz dolduruldu: %d sağlıklı proxy (toplam havuz: %d)",
                len(healthy_proxies),
                self._pool.size(),
            )

    async def _shutdown(self) -> None:
        """Temiz kapatma — bekleyen refill task'ını iptal et, oturumları kapat."""
        logger.info("AsyncGhostBooster kapatılıyor...")
        # Arka plan refill task'ını iptal et
        if self._refill_task is not None and not self._refill_task.done():
            self._refill_task.cancel()
            try:
                await self._refill_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._session_manager is not None:
            await self._session_manager.close_all()
        logger.info("AsyncGhostBooster kapatıldı")
