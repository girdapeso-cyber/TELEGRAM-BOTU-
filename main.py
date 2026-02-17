"""KRBRZ Network Stress Tester - Ana giriş noktası."""

import threading
import time
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

from config import load_configuration
from src.bot_controller import BotController

# Self-ping aralığı (saniye) — HF Spaces uyku moduna girmesin
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
    """Kendi health endpoint'ine periyodik ping atarak HF Spaces'i uyanık tutar."""
    while True:
        time.sleep(SELF_PING_INTERVAL)
        try:
            urllib.request.urlopen("http://localhost:7860", timeout=5)
        except Exception:
            pass


def main() -> None:
    """Bot'u yapılandırır ve başlatır."""
    # Health check server'ı arka planda başlat
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    # Self-ping thread'i — HF Spaces uyku moduna girmesin
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
