"""Proxy format algılama ve normalizasyon.

Farklı kaynaklardan gelen farklı formatlardaki proxy satırlarını
otomatik algılayıp standart ParsedProxy nesnesine dönüştürür.

Gereksinimler: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from src.models.proxy_models import ParsedProxy

logger = logging.getLogger(__name__)


class ProxyFormatParser:
    """Proxy format algılama ve normalizasyon.

    Farklı kaynaklardan gelen farklı formatlardaki proxy satırlarını
    otomatik algılayıp standart ParsedProxy nesnesine dönüştürür.
    """

    SUPPORTED_PROTOCOLS = {"http", "https", "socks5"}

    def parse(self, raw_line: str) -> ParsedProxy | None:
        """Tek bir proxy satırını ayrıştırır.

        Desteklenen formatlar:
        - ip:port → HTTP olarak varsayılır
        - ip:port:user:pass → Kimlik doğrulamalı HTTP
        - protocol://ip:port → Protokol korunur
        - protocol://user:pass@ip:port → Tüm bileşenler korunur

        Tanınmayan format → None döner, hata loglanır.
        """
        line = raw_line.strip()
        if not line:
            return None

        if "://" in line:
            return self._parse_url_format(line)
        return self._parse_plain_format(line)

    def format(self, proxy: ParsedProxy) -> str:
        """ParsedProxy nesnesini standart string formatına dönüştürür.

        Kimlik doğrulamalı: protocol://user:pass@host:port
        Kimlik doğrulamasız: protocol://host:port
        """
        if proxy.username and proxy.password:
            return f"{proxy.protocol}://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
        return f"{proxy.protocol}://{proxy.host}:{proxy.port}"

    def parse_many(self, raw_text: str) -> list[ParsedProxy]:
        """Çok satırlı metni satır satır ayrıştırır, geçersiz satırları atlar."""
        results: list[ParsedProxy] = []
        for line in raw_text.splitlines():
            parsed = self.parse(line)
            if parsed is not None:
                results.append(parsed)
        return results

    def _parse_url_format(self, line: str) -> ParsedProxy | None:
        """protocol://[user:pass@]host:port formatını ayrıştırır."""
        try:
            parsed = urlparse(line)
            protocol = parsed.scheme.lower()
            if protocol not in self.SUPPORTED_PROTOCOLS:
                logger.warning("Tanınmayan protokol: %s (satır: %s)", protocol, line)
                return None

            host = parsed.hostname
            port = parsed.port
            if not host or port is None:
                logger.warning("Tanınmayan proxy formatı: %s", line)
                return None

            if not self._validate_port(port):
                logger.warning("Geçersiz port numarası: %d (satır: %s)", port, line)
                return None

            username = parsed.username or None
            password = parsed.password or None

            return ParsedProxy(
                protocol=protocol,
                host=host,
                port=port,
                username=username,
                password=password,
            )
        except Exception:
            logger.warning("Tanınmayan proxy formatı: %s", line)
            return None

    def _parse_plain_format(self, line: str) -> ParsedProxy | None:
        """ip:port veya ip:port:user:pass formatını ayrıştırır."""
        parts = line.split(":")
        colon_count = len(parts) - 1

        if colon_count == 1:
            # ip:port → HTTP
            host, port_str = parts[0], parts[1]
            return self._build_proxy("http", host, port_str, line)

        if colon_count == 3:
            # ip:port:user:pass → HTTP with auth
            host, port_str, username, password = parts[0], parts[1], parts[2], parts[3]
            return self._build_proxy("http", host, port_str, line, username, password)

        logger.warning("Tanınmayan proxy formatı: %s", line)
        return None

    def _build_proxy(
        self,
        protocol: str,
        host: str,
        port_str: str,
        raw_line: str,
        username: str | None = None,
        password: str | None = None,
    ) -> ParsedProxy | None:
        """Port doğrulaması yaparak ParsedProxy oluşturur."""
        try:
            port = int(port_str)
        except ValueError:
            logger.warning("Port sayısal değil: %s (satır: %s)", port_str, raw_line)
            return None

        if not self._validate_port(port):
            logger.warning("Geçersiz port numarası: %d (satır: %s)", port, raw_line)
            return None

        return ParsedProxy(
            protocol=protocol,
            host=host,
            port=port,
            username=username,
            password=password,
        )

    @staticmethod
    def _validate_port(port: int) -> bool:
        """Port numarasının 1-65535 aralığında olduğunu doğrular."""
        return 1 <= port <= 65535
