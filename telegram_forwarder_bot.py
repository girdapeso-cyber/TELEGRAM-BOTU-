# -*- coding: utf-8 -*-
"""
Bu bot, Gemini AI entegrasyonu ile metinleri otomatik olarak iyileştirebilen ve
fotoğraflara filigran ekleyebilen, Render platformunda 7/24 çalışmak üzere
tasarlanmış bir içerik asistanıdır. Yapay zeka, KRBRZ VIP kanalının kimliğine
uygun olarak, havalı bir Pro Gamer/Hacker gibi metinler üretmek üzere özel
olarak eğitilmiştir.
(Hedef kanal butonu ve ana aktarma fonksiyonu hataları düzeltildi.)
"""

# --- Gerekli Kütüphaneler ---
import os
import logging
import json
import io
from threading import Thread
import httpx
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes,
    ConversationHandler, CallbackQueryHandler
)
from flask import Flask

# --- Güvenli Bilgi Alımı (Render Environment Variables) ---
try:
    BOT_TOKEN = os.environ['BOT_TOKEN']
    ADMIN_USER_ID = int(os.environ['ADMIN_USER_ID'])
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') 
except (KeyError, ValueError):
    print("!!! HATA: BOT_TOKEN, ADMIN_USER_ID veya GEMINI_API_KEY ortam değişkenleri bulunamadı!")
    exit()

# --- Genel Ayarlar ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Ayarları Kaydetme ve Yükleme ---
CONFIG_FILE = "bot_config.json"

def load_config():
    """Ayarları dosyadan yükler."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
    else:
        # Varsayılan ayarlar
        config = {
            "source_channels": [], 
            "destination_channels": [],
            "is_paused": False,
            "ai_enhancement_enabled": True,
            "watermark": {
                "text": "KRBRZ_VIP", 
                "position": "sag-alt", 
                "color": "beyaz", 
                "enabled": True
            }
        }
    config.setdefault("ai_enhancement_enabled", True)
    config.setdefault("watermark", {
        "text": "KRBRZ_VIP", "position": "sag-alt", "color": "beyaz", "enabled": True
    })
    return config

bot_config = load_config()

def save_config():
    """Ayarları dosyaya kaydeder."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(bot_config, f, indent=4, ensure_ascii=False)

# --- Yapay Zeka Fonksiyonu ---
async def enhance_caption_with_gemini(original_caption: str) -> str:
    if not GEMINI_API_KEY: return original_caption
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={GEMINI_API_KEY}"
    system_prompt = (
        "Sen, 'KRBRZ VIP' adında özel bir PUBG kanalının yöneticisisin. "
        "Tarzın havalı, gizemli ve profesyonel bir hacker/pro gamer gibi. "
        "Sana verilecek olan basit bir metni alıp, takipçileri heyecanlandıracak, "
        "özel ve ayrıcalıklı bir içeriğe baktıklarını hissettirecek bir duyuruya dönüştür. "
        "Bolca teknoloji, hedef ve zafer temalı emoji kullan (👑🎯💻💀🔥💯). "
        "Kendinden emin ve meydan okuyan bir dil kullan. Mutlaka #KRBRZ_VIP, #Bypass, #PUBGhack, #Gaming, #Win gibi içeriğe uygun hashtag'ler ekle. "
        "Metni, takipçileri daha fazlası için kanalda kalmaya teşvik eden bir eylem çağrısıyla bitir. Örneğin 'Sıradaki avı bekleyin.' veya 'KRBRZ VIP farkıyla.' gibi. "
        "Cevabın sadece ve sadece oluşturduğun yeni metin olsun, başka hiçbir açıklama ekleme."
    )
    payload = {"contents": [{"parts": [{"text": original_caption}]}], "systemInstruction": {"parts": [{"text": system_prompt}]}}
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(api_url, json=payload, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            result = response.json()
            enhanced_text = result["candidates"][0]["content"]["parts"][0]["text"]
            logger.info("Metin, Gemini AI tarafından (KRBRZ VIP Modu) başarıyla iyileştirildi.")
            return enhanced_text.strip()
    except Exception as e:
        logger.error(f"Gemini API hatası: {e}")
        return original_caption

# --- Filigran Fonksiyonu ---
async def apply_watermark(photo_bytes: bytes) -> bytes:
    wm_config = bot_config.get("watermark", {})
    if not wm_config.get("enabled") or not wm_config.get("text"):
        return photo_bytes
    try:
        with Image.open(io.BytesIO(photo_bytes)).convert("RGBA") as base:
            txt = Image.new("RGBA", base.size, (255, 255, 255, 0))
            try: font = ImageFont.truetype("arial.ttf", size=max(15, base.size[1] // 25))
            except IOError: font = ImageFont.load_default()
            d = ImageDraw.Draw(txt)
            colors = {"beyaz": (255, 255, 255, 128), "siyah": (0, 0, 0, 128), "kirmizi": (255, 0, 0, 128)}
            fill_color = colors.get(wm_config.get("color", "beyaz").lower(), (255, 255, 255, 128))
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

# --- Yönetici Güvenlik Filtresi ---
def admin_only(func):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user.id != ADMIN_USER_ID: return
        return await func(update, context, *args, **kwargs)
    return wrapped

# --- Kurulum Sihirbazı ---
SETUP_MENU, GET_SOURCE, GET_DEST, GET_WATERMARK_TEXT = range(4)

@admin_only
async def setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """/ayarla komutu ile sihirbazı başlatır ve ana menüyü gösterir."""
    ai_status = "✅ Aktif" if bot_config.get("ai_enhancement_enabled") else "❌ Pasif"
    wm_status = f"✅ Aktif ({bot_config['watermark']['text']})" if bot_config['watermark'].get('enabled') else "❌ Pasif"
    keyboard = [
        [
            InlineKeyboardButton("Kaynak Kanallar", callback_data='set_source'),
            InlineKeyboardButton("Hedef Kanallar", callback_data='set_dest')
        ],
        [InlineKeyboardButton(f"Yapay Zeka: {ai_status}", callback_data='toggle_ai')],
        [InlineKeyboardButton(f"Filigran: {wm_status}", callback_data='set_watermark')],
        [InlineKeyboardButton("✅ Sihirbazdan Çık", callback_data='exit_setup')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_content = "Bot ayarlarını yönetin:"
    if update.message:
        await update.message.reply_text(message_content, reply_markup=reply_markup)
    elif update.callback_query:
        try:
            await update.callback_query.edit_message_text(message_content, reply_markup=reply_markup)
        except Exception:
            # Mesaj değişmediyse hata verir, görmezden gelip devam edebiliriz.
            pass
        
    return SETUP_MENU

async def setup_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Menüdeki butonlara basıldığında ilgili adıma yönlendirir."""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == 'set_source':
        current = ", ".join(bot_config['source_channels']) or "Yok"
        await query.edit_message_text(f"Mevcut Kaynaklar: {current}\n\nŞimdi, bu mesaja cevap olarak, dinlenecek kaynak kanalın adını yazıp gönderin (@ile).")
        return GET_SOURCE
    elif data == 'set_dest':
        current = ", ".join(bot_config['destination_channels']) or "Yok"
        await query.edit_message_text(f"Mevcut Hedefler: {current}\n\nŞimdi, bu mesaja cevap olarak, gönderilerin yapılacağı hedef kanalın adını yazıp gönderin.")
        return GET_DEST
    elif data == 'toggle_ai':
        bot_config["ai_enhancement_enabled"] = not bot_config.get("ai_enhancement_enabled", False)
        save_config()
        return await setup_command(query, context)
    elif data == 'set_watermark':
        await query.edit_message_text("Yeni filigran metnini girin. Kapatmak için 'kapat' yazın.")
        return GET_WATERMARK_TEXT
    elif data == 'exit_setup':
        await query.edit_message_text("Kurulum kapatıldı.")
        return ConversationHandler.END
    return SETUP_MENU

async def channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, channel_type: str) -> int:
    """Kullanıcıdan gelen kanal adını işler ve menüye geri döner."""
    channel = update.message.text.strip()
    config_key = f"{channel_type}_channels"
    if channel in bot_config[config_key]:
        bot_config[config_key].remove(channel)
        await update.message.reply_text(f"🗑️ {channel_type.capitalize()} silindi: {channel}")
    else:
        bot_config[config_key].append(channel)
        await update.message.reply_text(f"✅ {channel_type.capitalize()} eklendi: {channel}")
    save_config()
    await setup_command(update, context)
    return ConversationHandler.END
    
async def get_source_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await channel_handler(update, context, "source")

async def get_dest_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await channel_handler(update, context, "destination")

async def get_watermark_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text.lower() == 'kapat':
        bot_config['watermark']['enabled'] = False
        await update.message.reply_text("❌ Filigran kapatıldı.")
    else:
        bot_config['watermark']['text'] = text
        bot_config['watermark']['enabled'] = True
        await update.message.reply_text(f"✅ Filigran metni ayarlandı: '{text}'")
    save_config()
    await setup_command(update, context)
    return ConversationHandler.END

async def cancel_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("İşlem iptal edildi.")
    return ConversationHandler.END

# --- YENİLENMİŞ Ana Aktarma Fonksiyonu ---
async def forwarder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if bot_config.get("is_paused", False): return
    message = update.channel_post
    if not message: return
    
    chat_identifier = f"@{message.chat.username}" if message.chat.username else str(message.chat.id)
    if chat_identifier not in bot_config["source_channels"]: return

    original_text = message.caption or message.text or ""
    final_text = original_text

    if bot_config.get("ai_enhancement_enabled") and original_text:
        await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
        final_text = await enhance_caption_with_gemini(original_text)

    for dest in bot_config["destination_channels"]:
        try:
            if message.photo:
                file = await context.bot.get_file(message.photo[-1].file_id)
                async with httpx.AsyncClient() as client:
                    photo_bytes = (await client.get(file.file_path)).content
                watermarked_photo = await apply_watermark(photo_bytes)
                await context.bot.send_photo(chat_id=dest, photo=watermarked_photo, caption=final_text)
            elif message.video:
                await message.copy(chat_id=dest, caption=final_text)
            elif message.text:
                await context.bot.send_message(chat_id=dest, text=final_text)
            else: # Diğer her şey (sticker, anket vb.)
                await message.copy(chat_id=dest)
            logger.info(f"Gönderi '{dest}' kanalına başarıyla aktarıldı.")
        except Exception as e:
            logger.error(f"Aktarma hatası ({dest}): {e}")

# --- Render için Web Sunucusu ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return "Yapay zeka ve filigran destekli KRBRZ VIP bot sunucusu ayakta."

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    flask_app.run(host='0.0.0.0', port=port)

# --- Botu Başlatma ---
def main():
    logger.info("Yapay zeka ve filigran destekli KRBRZ VIP botu başlatılıyor...")
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("ayarla", setup_command)],
        states={
            SETUP_MENU: [CallbackQueryHandler(setup_menu_handler)],
            GET_SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_source_handler)],
            GET_DEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_dest_handler)],
            GET_WATERMARK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_watermark_text_handler)],
        },
        fallbacks=[CommandHandler("iptal", cancel_setup)],
        per_message=False
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Ayarları yapmak için /ayarla komutunu kullanın.")))
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, forwarder))
    
    logger.info("Bot çalışıyor ve komutları bekliyor.")
    application.run_polling()

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    main()

