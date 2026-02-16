"""KRBRZ Network Stress Tester - Ana giriş noktası.

Configuration yükler, BotController başlatır ve graceful shutdown sağlar.

Gereksinimler:
    1.1: Target_Channel'ı sürekli olarak dinleme
"""

from config import load_configuration
from src.bot_controller import BotController


def main() -> None:
    """Bot'u yapılandırır ve başlatır."""
    config = load_configuration()
    controller = BotController(config)

    print("Bot başlatılıyor...")

    try:
        controller.start()
    except KeyboardInterrupt:
        print("\nBot kapatılıyor...")


if __name__ == "__main__":
    main()
