# -*- coding: utf-8 -*-
"""
Bu bot, Render platformunda 7/24 çalışmak üzere tasarlanmıştır.
Tüm ayarlar ve komutlar bu tek dosya içindedir.
"""

# --- Gerekli Kütüphaneler ---
import os
import logging
import io
from threading import Thread
import httpx
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask

# --- Güvenli Bilgi Alımı ---
# BU BİLGİLER RENDER > ENVIRONMENT VARIABLES KISMINDAN ALINACAKTIR.
# KODUN İÇİNE YAZMAYIN!
try:
    BOT_TOKEN = os.environ['BOT_TOKEN']
    ADMIN_USER_ID = int(os.environ['ADMIN_USER_ID'])
except (KeyError, ValueError):
    print("!!! HATA: BOT_TOKEN veya ADMIN_USER_ID ortam değişkenleri bulunamadı!")
    print("!!! Lütfen Render > Environment kısmından bu iki değişkeni ayarlayın.")
    exit()

# --- Genel Ayarlar ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Botun Hafızası (Ayarları Buradan Değiştirebilirsiniz) ---
bot_config = {
    "source_channels": ["@kaynakwkanal"],
    "destination_channels": ["@KRBZ_VIP_TR"],
    "custom_message": "🚀 Harika bir içerik daha! 🚀\n\nBizi takip etmeye devam edin!",
    "button_text": None,
    "button_url": None,
    "replacements": {},
    "is_paused": False,
    "forwarding_mode": "hepsi", # "hepsi" veya "filtreli"
    "trigger_keywords": [],
    "watermark": {
        "text": "KRBRZ VIP",
        "position": "sag-alt",
        "color": "white",
        "enabled": True
    }
}

# --- Yönetici Güvenlik Filtresi ---
def admin_only(func):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user.id != ADMIN_USER_ID:
            await update.message.reply_text("⛔ Bu komutu kullanma yetkiniz yok.")
            return
        await func(update, context, *args, **kwargs)
    return wrapped

# --- Filigran Fonksiyonu ---
async def apply_watermark(photo_bytes: bytes) -> bytes:
    wm_config = bot_config.get("watermark", {})
    if not wm_config.get("enabled") or not wm_config.get("text"):
        return photo_bytes
    try:
        with Image.open(io.BytesIO(photo_bytes)).convert("RGBA") as base:
            txt = Image.new("RGBA", base.size, (255, 255, 255, 0))
            try:
                font = ImageFont.truetype("arial.ttf", size=max(15, base.size[1] // 25))
            except IOError:
                font = ImageFont.load_default()
            d = ImageDraw.Draw(txt)
            colors = {"white": (255, 255, 255, 128), "black": (0, 0, 0, 128), "red": (255, 0, 0, 128)}
            fill_color = colors.get(wm_config.get("color", "white").lower(), (255, 255, 255, 128))
            text_bbox = d.textbbox((0, 0), wm_config["text"], font=font)
            text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
            margin = 15
            position_map = {
                'sol-ust': (margin, margin), 'orta-ust': ((base.width - text_width) / 2, margin), 'sag-ust': (base.width - text_width - margin, margin),
                'sol-orta': (margin, (base.height - text_height) / 2), 'orta': ((base.width - text_width) / 2, (base.height - text_height) / 2), 'sag-orta': (base.width - text_width - margin, (base.height - text_height) / 2),
                'sol-alt': (margin, base.height - text_height - margin), 'orta-alt': ((base.width - text_width) / 2, base.height - text_height - margin), 'sag-alt': (base.width - text_width - margin, base.height - text_height - margin)
            }
            x, y = position_map.get(wm_config.get("position", "sag-alt"), position_map['sag-alt'])
            d.text((x, y), wm_config["text"], font=font, fill=fill_color)
            out = Image.alpha_composite(base, txt)
            buffer = io.BytesIO()
            out.convert("RGB").save(buffer, format="JPEG")
            buffer.seek(0)
            return buffer.getvalue()
    except Exception as e:
        logger.error(f"Filigran hatası: {e}")
        return photo_bytes

# --- Komut Fonksiyonları ---
@admin_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Merhaba! Bot aktif ve çalışıyor.")

# --- Ana Aktarma Fonksiyonu ---
async def forwarder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if bot_config["is_paused"]: return
    message = update.channel_post
    if not message: return
    
    chat_identifier = f"@{message.chat.username}" if message.chat.username else str(message.chat.id)
    if chat_identifier not in bot_config["source_channels"]: return

    for dest in bot_config["destination_channels"]:
        try:
            if message.photo and bot_config["watermark"]["enabled"]:
                file = await context.bot.get_file(message.photo[-1].file_id)
                async with httpx.AsyncClient() as client:
                    photo_bytes = (await client.get(file.file_path)).content
                watermarked_photo = await apply_watermark(photo_bytes)
                await context.bot.send_photo(chat_id=dest, photo=watermarked_photo, caption=message.caption)
            else:
                await message.copy(chat_id=dest)
            logger.info(f"Gönderi '{dest}' kanalına başarıyla aktarıldı.")
        except Exception as e:
            logger.error(f"'{dest}' kanalına gönderim hatası: {e}")

# --- Render için Web Sunucusu ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return "Bot sunucusu ayakta."

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    flask_app.run(host='0.0.0.0', port=port)

# --- Botu Başlatma ---
def main():
    logger.info("Bot başlatılıyor...")
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Komutları ekle
    application.add_handler(CommandHandler("start", start_command))
    
    # Ana dinleyiciyi ekle
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, forwarder))
    
    logger.info("Bot çalışıyor ve kanalları dinliyor.")
    application.run_polling()

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    main()
