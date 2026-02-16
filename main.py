"""KRBRZ Network Stress Tester - Ana giriş noktası."""

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from config import load_configuration
from src.bot_controller import BotController


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


def main() -> None:
    """Bot'u yapılandırır ve başlatır."""
    # Health check server'ı arka planda başlat
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    config = load_configuration()
    controller = BotController(config)

    print("Bot başlatılıyor...")

    try:
        controller.start()
    except KeyboardInterrupt:
        print("\nBot kapatılıyor...")


if __name__ == "__main__":
    main()
