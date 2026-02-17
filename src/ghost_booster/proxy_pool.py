"""Proxy havuzu yönetimi.

Sağlık kontrolünden geçmiş proxy'leri yönetir, kritik eşik kontrolü yapar
ve IP rotasyonu için acquire semantiği sağlar.

Gereksinimler: 4.1 (kritik eşik), 4.2 (IP rotasyonu), 4.3 (havuz tükenme), 4.4 (sıralı havuz)
"""

from __future__ import annotations

import logging
from collections import deque

from src.models.proxy_models import ParsedProxy

logger = logging.getLogger(__name__)


class ProxyPool:
    """Sağlıklı proxy'leri yöneten havuz.

    Proxy'ler yanıt süresine göre sıralı tutulur (en hızlı önce).
    acquire() ile alınan proxy havuzdan çıkarılır (IP rotasyonu).
    """

    def __init__(self, critical_threshold: int = 10) -> None:
        self._pool: deque[ParsedProxy] = deque()
        self._critical_threshold = critical_threshold

    def load(self, proxies: list[ParsedProxy]) -> None:
        """Sağlık kontrolünden geçmiş proxy'leri havuza yükler.

        Proxy'ler zaten yanıt süresine göre sıralı gelir (HealthChecker'dan).
        Mevcut havuzun sonuna eklenir.
        """
        self._pool.extend(proxies)
        logger.info("Havuza %d proxy yüklendi (toplam: %d)", len(proxies), len(self._pool))

    def acquire(self) -> ParsedProxy | None:
        """Havuzdan en hızlı proxy'yi alır ve havuzdan çıkarır.

        Returns:
            En hızlı proxy veya havuz boşsa None.
        """
        if not self._pool:
            return None
        proxy = self._pool.popleft()
        logger.debug("Proxy alındı: %s (kalan: %d)", proxy.to_key(), len(self._pool))
        return proxy

    def size(self) -> int:
        """Havuzdaki mevcut proxy sayısını döner."""
        return len(self._pool)

    def is_critical(self) -> bool:
        """Havuz kritik eşiğin altında mı kontrol eder."""
        return len(self._pool) < self._critical_threshold

    def is_empty(self) -> bool:
        """Havuz tamamen boş mu kontrol eder."""
        return len(self._pool) == 0
