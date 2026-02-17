"""KRBRZ Network Stress Tester - Ana giriş noktası."""

import os
import threading
import time
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

from config import load_configuration
from src.bot_controller import BotController

# Self-ping aralığı (saniye) — Koyeb Scale-to-Zero'yu önlemek için
SELF_PING_INTERVAL = 300  # 5 dakika


class HealthHandler(BaseHTTPRequestHandler):
    """HF Spaces health check için basit HTTP handler."""
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass  # Log spam'i engelle


def start_health_server():
    """Port 7860'da health check server başlatır."""
    server = HTTPServer(("0.0.0.0", 7860), HealthHandler)
    server.serve_forever()


def self_ping_loop():
    """Public URL'e periyodik ping atarak Koyeb Scale-to-Zero'yu önler.

    Koyeb sadece dışarıdan gelen trafiği sayar. Localhost ping'i işe yaramaz.
    KOYEB_PUBLIC_DOMAIN veya APP_URL env var'ından public URL alınır.
    Bulunamazsa localhost'a fallback yapar.
    """
    # Koyeb otomatik olarak KOYEB_PUBLIC_DOMAIN env var'ını set eder
    public_domain = os.environ.get("KOYEB_PUBLIC_DOMAIN", "")
    app_url = os.environ.get("APP_URL", "")

    if public_domain:
        ping_url = f"https://{public_domain}"
    elif app_url:
        ping_url = app_url.rstrip("/")
    else:
        ping_url = "http://localhost:7860"

    print(f"Self-ping aktif: {ping_url} (her {SELF_PING_INTERVAL}s)")

    while True:
        time.sleep(SELF_PING_INTERVAL)
        try:
            urllib.request.urlopen(ping_url, timeout=10)
        except Exception:
            pass


def main() -> None:
    """Bot'u yapılandırır ve başlatır."""
    # Health check server'ı arka planda başlat
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    # Self-ping thread'i — Koyeb Scale-to-Zero'yu önle
    ping_thread = threading.Thread(target=self_ping_loop, daemon=True)
    ping_thread.start()

    config = load_configuration()
    print("Bot başlatılıyor...")

    while True:
        try:
            controller = BotController(config)
            controller.start()
            break
        except KeyboardInterrupt:
            print("\nBot kapatılıyor...")
            break
        except Exception as e:
            print(f"Bot hatası: {e}")
            print("10 saniye sonra tekrar denenecek...")
            time.sleep(10)


if __name__ == "__main__":
    main()
