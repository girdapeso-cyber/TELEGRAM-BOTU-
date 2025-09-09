# -*- coding: utf-8 -*-
"""
Bu bot, Render platformunda 7/24 çalışmak üzere tasarlanmış tam sürüm bir bottur.
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

# --- Güvenli Bilgi Alımı (Render Environment Variables) ---
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

# --- Filigran Fonksiyonları ---
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
            colors = {"beyaz": (255, 255, 255, 128), "siyah": (0, 0, 0, 128), "kirmizi": (255, 0, 0, 128)}
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

# --- Tüm Komut Fonksiyonları ---

@admin_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Merhaba! Bot aktif ve çalışıyor. Komut listesi için /yardim yazabilirsiniz.")

@admin_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
*Genel Kontrol*
/durdur - Aktarımı durdurur.
/devam - Aktarımı başlatır.
/durum - Botun durumunu gösterir.

*Kaynak Kanallar*
/ekle <@kanal> - Kaynak ekler.
/cikar <@kanal> - Kaynak çıkarır.
/listele - Kaynakları listeler.

*Hedef Kanallar*
/hedef_ekle <@kanal> - Hedef ekler.
/hedef_cikar <@kanal> - Hedef çıkarır.
/hedef_listele - Hedefleri listeler.

*Filigran Ayarları*
/filigran_ekle <metin>
/filigran_sil
/filigran_konum <konum>
/filigran_renk <renk>

*İçerik Ayarları*
/mesaj <yeni mesaj>
/buton_ekle <metin> <link>
/buton_sil
/degistir <eski> <yeni>
/kaldir_degisim <eski>
/degisim_listesi
/duyuru <mesaj>
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

@admin_only
async def pause_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_config["is_paused"] = True
    await update.message.reply_text("🔴 Bot duraklatıldı.")

@admin_only
async def resume_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_config["is_paused"] = False
    await update.message.reply_text("🟢 Bot yeniden aktif.")

@admin_only
async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "🔴 Duraklatıldı" if bot_config["is_paused"] else "🟢 Aktif"
    await update.message.reply_text(f"Bot Durumu: {status}")

@admin_only
async def add_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Kullanım: /ekle <@kanal_adi>"); return
    channel = context.args[0]
    if channel not in bot_config["source_channels"]:
        bot_config["source_channels"].append(channel)
        await update.message.reply_text(f"✅ Kaynak eklendi: {channel}")
    else: await update.message.reply_text(f"⚠️ Zaten listede: {channel}")

@admin_only
async def remove_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Kullanım: /cikar <@kanal_adi>"); return
    channel = context.args[0]
    if channel in bot_config["source_channels"]:
        bot_config["source_channels"].remove(channel)
        await update.message.reply_text(f"🗑️ Kaynak çıkarıldı: {channel}")
    else: await update.message.reply_text(f"❓ Listede bulunamadı: {channel}")

@admin_only
async def list_sources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_config["source_channels"]: await update.message.reply_text("Kaynak kanal listesi boş."); return
    await update.message.reply_text("📜 Kaynak Kanallar:\n" + "\n".join(bot_config["source_channels"]))

@admin_only
async def add_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Kullanım: /hedef_ekle <@kanal_adi>"); return
    channel = context.args[0]
    if channel not in bot_config["destination_channels"]:
        bot_config["destination_channels"].append(channel)
        await update.message.reply_text(f"✅ Hedef eklendi: {channel}")
    else: await update.message.reply_text(f"⚠️ Zaten listede: {channel}")

@admin_only
async def remove_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Kullanım: /hedef_cikar <@kanal_adi>"); return
    channel = context.args[0]
    if channel in bot_config["destination_channels"]:
        bot_config["destination_channels"].remove(channel)
        await update.message.reply_text(f"🗑️ Hedef çıkarıldı: {channel}")
    else: await update.message.reply_text(f"❓ Listede bulunamadı: {channel}")

@admin_only
async def list_destinations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_config["destination_channels"]: await update.message.reply_text("Hedef kanal listesi boş."); return
    await update.message.reply_text("🎯 Hedef Kanallar:\n" + "\n".join(bot_config["destination_channels"]))

@admin_only
async def set_watermark_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        bot_config["watermark"]["enabled"] = not bot_config["watermark"]["enabled"]
        status = "aktif" if bot_config["watermark"]["enabled"] else "pasif"
        await update.message.reply_text(f"🖼️ Filigran şimdi {status}.")
        return
    text = " ".join(context.args)
    bot_config["watermark"]["text"] = text
    bot_config["watermark"]["enabled"] = True
    await update.message.reply_text(f"✅ Filigran metni ayarlandı: '{text}'")

@admin_only
async def remove_watermark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_config["watermark"]["enabled"] = False
    await update.message.reply_text("🗑️ Filigran kapatıldı.")

@admin_only
async def set_watermark_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    positions = ['sol-ust', 'orta-ust', 'sag-ust', 'sol-orta', 'orta', 'sag-orta', 'sol-alt', 'orta-alt', 'sag-alt']
    if not context.args or context.args[0].lower() not in positions:
        await update.message.reply_text(f"Geçerli konumlar: {', '.join(positions)}")
        return
    position = context.args[0].lower()
    bot_config["watermark"]["position"] = position
    await update.message.reply_text(f"✅ Filigran konumu '{position}' olarak ayarlandı.")

@admin_only
async def set_watermark_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    colors = ['beyaz', 'siyah', 'kirmizi']
    if not context.args or context.args[0].lower() not in colors:
        await update.message.reply_text(f"Geçerli renkler: {', '.join(colors)}")
        return
    color = context.args[0].lower()
    bot_config["watermark"]["color"] = color
    await update.message.reply_text(f"✅ Filigran rengi '{color}' olarak ayarlandı.")
    
@admin_only
async def set_message_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Kullanım: /mesaj <yeni mesaj>"); return
    bot_config["custom_message"] = " ".join(context.args)
    await update.message.reply_text(f"✅ Yeni otomatik mesaj ayarlandı.")

@admin_only
async def set_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2: await update.message.reply_text('Kullanım: /buton_ekle <metin> <link>'); return
    bot_config["button_url"] = context.args[-1]
    bot_config["button_text"] = " ".join(context.args[:-1])
    await update.message.reply_text(f"✅ Buton ayarlandı.")

@admin_only
async def remove_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_config["button_text"] = None
    bot_config["button_url"] = None
    await update.message.reply_text("🗑️ Buton kaldırıldı.")
    
@admin_only
async def set_replacement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2: await update.message.reply_text('Kullanım: /degistir <eski> <yeni> (silmek için "sil" yaz)'); return
    old, new = context.args[0], " ".join(context.args[1:])
    bot_config["replacements"][old] = "" if new.lower() == 'sil' else new
    await update.message.reply_text(f"✅ Değişim kuralı ayarlandı.")

@admin_only
async def remove_replacement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Kullanım: /kaldir_degisim <eski_kelime>"); return
    old = context.args[0]
    if old in bot_config["replacements"]:
        del bot_config["replacements"][old]
        await update.message.reply_text(f"🗑️ Değişim kuralı kaldırıldı.")
    else: await update.message.reply_text(f"❓ Kural bulunamadı.")

@admin_only
async def list_replacements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_config["replacements"]: await update.message.reply_text("Değişim kuralı yok."); return
    rules = "\n".join([f"'{k}' -> '{v or '[SİLİNECEK]'}'" for k, v in bot_config["replacements"].items()])
    await update.message.reply_text(f"📜 Değişim Kuralları:\n{rules}")

@admin_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_to_send = update.message.reply_to_message
    text = " ".join(context.args)
    if not message_to_send and not text:
        await update.message.reply_text("Kullanım: /duyuru <mesaj> veya bir medyaya yanıt verin."); return
    
    for dest in bot_config["destination_channels"]:
        try:
            if message_to_send: await message_to_send.copy(chat_id=dest, caption=text or message_to_send.caption)
            else: await context.bot.send_message(chat_id=dest, text=text)
        except Exception as e:
            logger.error(f"Duyuru hatası '{dest}': {e}")
    await update.message.reply_text("✅ Duyuru gönderildi.")

# --- Ana Aktarma Fonksiyonu ---
async def forwarder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if bot_config.get("is_paused", False): return
    message = update.channel_post
    if not message: return
    
    chat_identifier = f"@{message.chat.username}" if message.chat.username else str(message.chat.id)
    if chat_identifier not in bot_config["source_channels"]: return

    caption = message.caption or ""
    for old, new in bot_config["replacements"].items():
        caption = caption.replace(old, new)
    
    final_caption = f"{caption}\n\n{bot_config['custom_message']}".strip()
    
    reply_markup = None
    if bot_config.get("button_text") and bot_config.get("button_url"):
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(text=bot_config["button_text"], url=bot_config["button_url"])]])

    for dest in bot_config["destination_channels"]:
        try:
            if message.photo:
                file = await context.bot.get_file(message.photo[-1].file_id)
                async with httpx.AsyncClient() as client:
                    photo_bytes = (await client.get(file.file_path)).content
                watermarked_photo = await apply_watermark(photo_bytes)
                await context.bot.send_photo(chat_id=dest, photo=watermarked_photo, caption=final_caption, reply_markup=reply_markup)
            else:
                await message.copy(chat_id=dest, caption=final_caption, reply_markup=reply_markup)
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
    
    # Tüm komutları ekle
    command_handlers = [
        CommandHandler("start", start_command),
        CommandHandler("yardim", help_command),
        CommandHandler("durdur", pause_bot),
        CommandHandler("devam", resume_bot),
        CommandHandler("durum", show_status),
        CommandHandler("ekle", add_source),
        CommandHandler("cikar", remove_source),
        CommandHandler("listele", list_sources),
        CommandHandler("hedef_ekle", add_destination),
        CommandHandler("hedef_cikar", remove_destination),
        CommandHandler("hedef_listele", list_destinations),
        CommandHandler("filigran_ekle", set_watermark_text),
        CommandHandler("filigran_sil", remove_watermark),
        CommandHandler("filigran_konum", set_watermark_position),
        CommandHandler("filigran_renk", set_watermark_color),
        CommandHandler("mesaj", set_message_text),
        CommandHandler("buton_ekle", set_button),
        CommandHandler("buton_sil", remove_button),
        CommandHandler("degistir", set_replacement),
        CommandHandler("kaldir_degisim", remove_replacement),
        CommandHandler("degisim_listesi", list_replacements),
        CommandHandler("duyuru", broadcast)
    ]
    application.add_handlers(command_handlers)

    # Ana dinleyiciyi ekle
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, forwarder))
    
    logger.info("Bot çalışıyor ve kanalları dinliyor.")
    application.run_polling()

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    main()

