# -*- coding: utf-8 -*-

"""
A comprehensive Telegram bot to forward messages from source channels to destination channels
with advanced features like watermarking, text replacement, keyword filtering, and more.
Now with Flask for web hosting compatibility.
"""

# --- Check and Install Required Libraries ---
try:
    import httpx
    from PIL import Image, ImageDraw, ImageFont
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.error import TelegramError
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    from telegram.constants import ParseMode
    from flask import Flask
    from threading import Thread
except ImportError:
    print("="*60)
    print("!!! GEREKLİ KÜTÜPHANELER EKSİK !!!")
    print("Lütfen `pip install -r requirements.txt` komutunu çalıştırın.")
    input("Devam etmek için Enter'a basın...")
    exit()

import logging
import json
import io
import os
from pathlib import Path
from functools import wraps
import re

# --- BOT CONFIGURATION ---
BOT_TOKEN = None
ADMIN_USER_ID = None

CONFIG_FILE = Path("config.json")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def load_config():
    """
    Loads the configuration from environment variables first, then falls back to a file.
    """
    global BOT_TOKEN, ADMIN_USER_ID
    
    bot_token_env = os.environ.get("BOT_TOKEN")
    admin_id_env = os.environ.get("ADMIN_USER_ID")
    
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    else:
        config = {
            "bot_token": "YOUR_BOT_TOKEN_HERE",
            "admin_user_id": 0,
            "source_channels": [], "destination_channels": [],
            "custom_message": "", "button_text": None, "button_url": None,
            "replacements": {}, "is_paused": False, "forwarding_mode": "all",
            "trigger_keywords": [],
            "watermark": {"text": None, "position": "bottom-right", "color": "white", "enabled": False}
        }
        save_config(config)
        print(f"'{CONFIG_FILE}' oluşturuldu. Yerel test için düzenleyin.")
    
    BOT_TOKEN = bot_token_env or config.get("bot_token")
    try:
        ADMIN_USER_ID = int(admin_id_env) if admin_id_env else int(config.get("admin_user_id", 0))
    except (ValueError, TypeError):
        ADMIN_USER_ID = 0

    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or not ADMIN_USER_ID:
        print(f"!!! KRİTİK: 'BOT_TOKEN' ve 'ADMIN_USER_ID' ayarlanmamış. Lütfen bunları '{CONFIG_FILE}' dosyasında veya ortam değişkeni olarak ayarlayın.")
        exit()
        
    config.setdefault("source_channels", [])
    config.setdefault("destination_channels", [])
    config.setdefault("button_text", None)
    config.setdefault("button_url", None)
    config.setdefault("replacements", {})
    config.setdefault("is_paused", False)
    config.setdefault("forwarding_mode", "all")
    config.setdefault("trigger_keywords", [])
    config.setdefault("watermark", {"text": None, "position": "bottom-right", "color": "white", "enabled": False})

    return config

def save_config(config):
    safe_config = config.copy()
    if os.environ.get("BOT_TOKEN"):
        safe_config.pop("bot_token", None)
    if os.environ.get("ADMIN_USER_ID"):
        safe_config.pop("admin_user_id", None)
        
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(safe_config, f, indent=4, ensure_ascii=False)

bot_config = load_config()

def admin_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user.id != ADMIN_USER_ID:
            await update.message.reply_text("⛔ Bu komutu kullanma yetkiniz yok.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

def escape_markdown_v2(text: str) -> str:
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

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
                logger.warning("Arial font not found, falling back to default font.")
                font = ImageFont.load_default()
            d = ImageDraw.Draw(txt)
            colors = {"white": (255, 255, 255, 128), "black": (0, 0, 0, 128), "red": (255, 0, 0, 128)}
            fill_color = colors.get(wm_config.get("color", "white").lower(), (255, 255, 255, 128))
            text_bbox = d.textbbox((0, 0), wm_config["text"], font=font)
            text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
            margin = 15
            position = wm_config.get("position", "bottom-right")
            pos_map = {
                'top-left': (margin, margin), 'top-center': ((base.width - text_width) / 2, margin), 'top-right': (base.width - text_width - margin, margin),
                'center-left': (margin, (base.height - text_height) / 2), 'center': ((base.width - text_width) / 2, (base.height - text_height) / 2), 'center-right': (base.width - text_width - margin, (base.height - text_height) / 2),
                'bottom-left': (margin, base.height - text_height - margin), 'bottom-center': ((base.width - text_width) / 2, base.height - text_height - margin), 'bottom-right': (base.width - text_width - margin, base.height - text_height - margin)
            }
            x, y = pos_map.get(position, pos_map['bottom-right'])
            d.text((x, y), wm_config["text"], font=font, fill=fill_color)
            out = Image.alpha_composite(base, txt)
            out_buffer = io.BytesIO()
            out.convert("RGB").save(out_buffer, format="JPEG")
            out_buffer.seek(0)
            return out_buffer.getvalue()
    except Exception as e:
        logger.error(f"Error applying watermark: {e}", exc_info=True)
        return photo_bytes

@admin_only
async def set_watermark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        bot_config["watermark"]["enabled"] = not bot_config["watermark"]["enabled"]
        status = "enabled" if bot_config["watermark"]["enabled"] else "disabled"
        await update.message.reply_text(f"🖼️ Watermark is now {status}.")
    else:
        text = " ".join(context.args)
        bot_config["watermark"]["text"] = text
        bot_config["watermark"]["enabled"] = True
        await update.message.reply_text(f"✅ Watermark text set to: '{text}' and enabled.")
    save_config(bot_config)

@admin_only
async def set_watermark_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    positions = ['top-left', 'top-center', 'top-right', 'center-left', 'center', 'center-right', 'bottom-left', 'bottom-center', 'bottom-right']
    if not context.args or context.args[0].lower() not in positions:
        await update.message.reply_text(f"Usage: /wm_pos <position>\nValid positions: {', '.join(positions)}")
        return
    bot_config["watermark"]["position"] = context.args[0].lower()
    save_config(bot_config)
    await update.message.reply_text(f"✅ Watermark position set to '{bot_config['watermark']['position']}'.")

@admin_only
async def set_watermark_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    colors = ['white', 'black', 'red']
    if not context.args or context.args[0].lower() not in colors:
        await update.message.reply_text(f"Usage: /wm_color <color>\nValid colors: {', '.join(colors)}")
        return
    bot_config["watermark"]["color"] = context.args[0].lower()
    save_config(bot_config)
    await update.message.reply_text(f"✅ Watermark color set to '{bot_config['watermark']['color']}'.")

@admin_only
async def add_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Usage: /add_source <channel_id or @username>"); return
    channel = context.args[0]
    if channel in bot_config["source_channels"]: await update.message.reply_text(f"⚠️ '{channel}' is already in the source list."); return
    try:
        await context.bot.get_chat(chat_id=channel)
        bot_config["source_channels"].append(channel)
        save_config(bot_config)
        await update.message.reply_text(f"✅ '{channel}' successfully added to source channels.")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Could not access channel '{channel}'. Is the bot an **Admin** there?\nError: {e}")

@admin_only
async def remove_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Usage: /remove_source <channel_id or @username>"); return
    channel = context.args[0]
    if channel in bot_config["source_channels"]:
        bot_config["source_channels"].remove(channel)
        save_config(bot_config)
        await update.message.reply_text(f"🗑️ '{channel}' removed from source channels.")
    else: await update.message.reply_text(f"❓ '{channel}' not found in the list.")

@admin_only
async def list_sources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_config["source_channels"]: await update.message.reply_text("No source channels are being monitored."); return
    channels_list = "\n".join(f"- {ch}" for ch in bot_config["source_channels"])
    await update.message.reply_text(f"📜 Monitored Source Channels:\n{channels_list}")

@admin_only
async def add_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Usage: /add_dest <@channel>"); return
    channel = context.args[0]
    if channel not in bot_config["destination_channels"]:
        bot_config["destination_channels"].append(channel)
        save_config(bot_config)
        await update.message.reply_text(f"✅ '{channel}' added to destination channels.")
    else: await update.message.reply_text(f"⚠️ '{channel}' is already in the destination list.")

@admin_only
async def remove_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Usage: /remove_dest <@channel>"); return
    channel = context.args[0]
    if channel in bot_config["destination_channels"]:
        bot_config["destination_channels"].remove(channel)
        save_config(bot_config)
        await update.message.reply_text(f"🗑️ '{channel}' removed from destination channels.")
    else: await update.message.reply_text(f"❓ '{channel}' not found in the destination list.")

@admin_only
async def list_destinations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_config["destination_channels"]: await update.message.reply_text("No destination channels are defined."); return
    channels_list = "\n".join(f"- {ch}" for ch in bot_config["destination_channels"])
    await update.message.reply_text(f"🎯 Destination Channels:\n{channels_list}")

@admin_only
async def set_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Usage: /set_message <your new automatic message>"); return
    bot_config["custom_message"] = " ".join(context.args)
    save_config(bot_config)
    await update.message.reply_text(f"✅ New automatic message set:\n\n{bot_config['custom_message']}")

@admin_only
async def set_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2: await update.message.reply_text('Usage: /add_button <Button Text> <URL>'); return
    url, text = context.args[-1], " ".join(context.args[:-1])
    if not (url.startswith('http://') or url.startswith('https://')): await update.message.reply_text('❌ Invalid URL!'); return
    bot_config["button_text"], bot_config["button_url"] = text, url
    save_config(bot_config)
    await update.message.reply_text(f"✅ Button configured!\nText: {text}\nURL: {url}")

@admin_only
async def remove_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_config["button_text"], bot_config["button_url"] = None, None
    save_config(bot_config)
    await update.message.reply_text("🗑️ Automatic button successfully removed.")

@admin_only
async def set_replacement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2: await update.message.reply_text('Usage: /replace <old> <new> (use "none" to delete)'); return
    old_word, new_word = context.args[0], " ".join(context.args[1:])
    if new_word.lower() == 'none': new_word = ""
    bot_config["replacements"][old_word] = new_word
    save_config(bot_config)
    await update.message.reply_text(f"✅ '{old_word}' will be replaced with '{new_word or '[DELETE]'}'.")

@admin_only
async def remove_replacement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Usage: /remove_replace <word_to_remove>"); return
    old_word = context.args[0]
    if old_word in bot_config["replacements"]:
        del bot_config["replacements"][old_word]
        save_config(bot_config)
        await update.message.reply_text(f"🗑️ Rule for '{old_word}' has been removed.")
    else: await update.message.reply_text(f"❓ No rule found for '{old_word}'.")

@admin_only
async def list_replacements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_config["replacements"]: await update.message.reply_text("No word replacement rules are defined."); return
    rules_list = "\n".join(f"- '{old}' -> '{new or '[DELETE]'}'" for old, new in bot_config["replacements"].items())
    await update.message.reply_text(f"📜 Active Replacement Rules:\n{rules_list}")

@admin_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    replied_message, broadcast_text = update.message.reply_to_message, " ".join(context.args)
    if not replied_message and not broadcast_text: await update.message.reply_text("Usage: `/broadcast <message>` or reply to media with `/broadcast <caption>`"); return
    success_count = 0
    for channel in bot_config["destination_channels"]:
        try:
            if replied_message: await replied_message.copy(chat_id=channel, caption=broadcast_text or replied_message.caption)
            else: await context.bot.send_message(chat_id=channel, text=broadcast_text)
            success_count += 1
        except Exception as e: await update.message.reply_text(f"❌ Failed to send to '{channel}': {e}")
    await update.message.reply_text(f"✅ Your broadcast was sent to {success_count} of {len(bot_config['destination_channels'])} targets.")

@admin_only
async def pause_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_config["is_paused"] = True
    save_config(bot_config)
    await update.message.reply_text("🔴 Bot paused. New posts will not be forwarded.")

@admin_only
async def resume_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_config["is_paused"] = False
    save_config(bot_config)
    await update.message.reply_text("🟢 Bot resumed. New posts will now be forwarded.")

@admin_only
async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "🔴 Paused" if bot_config.get("is_paused", False) else "🟢 Active"
    mode = "Filtered" if bot_config.get("forwarding_mode") == "filtered" else "All"
    await update.message.reply_text(f"Bot Status: {status}\nForwarding Mode: {mode}")

@admin_only
async def set_forwarding_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0].lower() not in ['all', 'filtered']: await update.message.reply_text("Usage: /mode <all|filtered>"); return
    mode = context.args[0].lower()
    bot_config["forwarding_mode"] = mode
    save_config(bot_config)
    await update.message.reply_text(f"✅ Mode changed: {'Normal' if mode == 'all' else 'Filter'} Mode.")

@admin_only
async def add_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Usage: /add_keyword <keyword>"); return
    keyword = " ".join(context.args).lower()
    if keyword not in bot_config["trigger_keywords"]:
        bot_config["trigger_keywords"].append(keyword)
        save_config(bot_config)
        await update.message.reply_text(f"✅ Keyword added: '{keyword}'")
    else: await update.message.reply_text(f"⚠️ '{keyword}' is already in the list.")

@admin_only
async def remove_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Usage: /remove_keyword <keyword>"); return
    keyword = " ".join(context.args).lower()
    if keyword in bot_config["trigger_keywords"]:
        bot_config["trigger_keywords"].remove(keyword)
        save_config(bot_config)
        await update.message.reply_text(f"🗑️ Keyword removed: '{keyword}'")
    else: await update.message.reply_text(f"❓ '{keyword}' not found in the list.")

@admin_only
async def list_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_config["trigger_keywords"]: await update.message.reply_text("No trigger keywords are defined."); return
    keywords_list = "\n".join(f"- {kw}" for kw in bot_config["trigger_keywords"])
    await update.message.reply_text(f"🔑 Active Keywords:\n{keywords_list}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_USER_ID:
        help_text = (
            "🤖 *Bot Yönetim Komutları* 🤖\n\n"
            "*Genel Kontrol:*\n`/pause`, `/resume`, `/status`\n\n"
            "*Filigran Yönetimi:*\n`/set_watermark <metin>`, `/wm_pos <konum>`, `/wm_color <renk>`\n\n"
            "*Filtreleme Modu:*\n`/mode <all|filtered>`, `/add_keyword <kelime>`, `/remove_keyword <kelime>`, `/list_keywords`\n\n"
            "*Yayın ve Mesaj:*\n`/broadcast <mesaj>`, `/set_message <mesaj>`\n\n"
            "*Buton Yönetimi:*\n`/add_button <metin> <url>`, `/remove_button`\n\n"
            "*Kanal Yönetimi:*\n`/add_source`, `/remove_source`, `/list_sources`\n`/add_dest`, `/remove_dest`, `/list_dest`\n\n"
            "*Metin Değiştirme:*\n`/replace <eski> <yeni>`, `/remove_replace <eski>`, `/list_replaces`\n\n"
            "`/help` Bu menüyü gösterir\."
        )
        await update.message.reply_text(escape_markdown_v2(help_text), parse_mode=ParseMode.MARKDOWN_V2)
    else:
        await update.message.reply_text("Merhaba! Ben bir kanal içerik aktarma botuyum.")

async def forward_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if bot_config.get("is_paused", False): return
    message = update.channel_post
    if not message: return
    chat_identifier = f"@{message.chat.username}" if message.chat.username else str(message.chat.id)
    if chat_identifier not in bot_config["source_channels"]: return
    if bot_config.get("forwarding_mode") == "filtered":
        message_text = (message.text or message.caption or "").lower()
        if not any(keyword in message_text for keyword in bot_config.get("trigger_keywords", [])): return
    logger.info(f"Forwarding post from '{message.chat.title}'...")
    original_caption, custom_message = message.caption or "", bot_config.get("custom_message", "")
    modified_caption = original_caption
    for old, new in bot_config.get("replacements", {}).items(): modified_caption = modified_caption.replace(old, new)
    final_caption = f"{modified_caption}\n\n{custom_message}".strip() if custom_message else modified_caption
    reply_markup = None
    if bot_config.get("button_text") and bot_config.get("button_url"):
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(text=bot_config["button_text"], url=bot_config["button_url"])]])
    for destination in bot_config["destination_channels"]:
        try:
            if message.photo:
                file = await context.bot.get_file(message.photo[-1].file_id)
                async with httpx.AsyncClient() as client: photo_bytes = (await client.get(file.file_path)).content
                watermarked_photo_bytes = await apply_watermark(photo_bytes)
                await context.bot.send_photo(chat_id=destination, photo=watermarked_photo_bytes, caption=final_caption, reply_markup=reply_markup)
            else:
                await message.copy(chat_id=destination, caption=final_caption if message.caption is not None else None, reply_markup=reply_markup)
            logger.info(f"Successfully forwarded post to '{destination}'.")
        except Exception as e:
            logger.error(f"Failed to forward post to '{destination}'. Error: {e}", exc_info=True)

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is alive."

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

def main():
    logger.info("Starting up the Channel Forwarder Bot...")
    application = Application.builder().token(BOT_TOKEN).build()
    handlers = [
        CommandHandler("set_watermark", set_watermark), CommandHandler("wm_pos", set_watermark_position), CommandHandler("wm_color", set_watermark_color),
        CommandHandler("pause", pause_bot), CommandHandler("resume", resume_bot), CommandHandler("status", show_status),
        CommandHandler("mode", set_forwarding_mode), CommandHandler("add_keyword", add_keyword), CommandHandler("remove_keyword", remove_keyword), CommandHandler("list_keywords", list_keywords),
        CommandHandler("broadcast", broadcast),
        CommandHandler("add_source", add_source), CommandHandler("remove_source", remove_source), CommandHandler("list_sources", list_sources),
        CommandHandler("add_dest", add_destination), CommandHandler("remove_dest", remove_destination), CommandHandler("list_dest", list_destinations),
        CommandHandler("set_message", set_message), CommandHandler("add_button", set_button), CommandHandler("remove_button", remove_button),
        CommandHandler("replace", set_replacement), CommandHandler("remove_replace", remove_replacement), CommandHandler("list_replaces", list_replacements),
        CommandHandler(["start", "help"], help_command),
        MessageHandler(filters.UpdateType.CHANNEL_POST, forward_channel_post)
    ]
    application.add_handlers(handlers)
    logger.info("Bot is running and waiting for commands and channel posts...")
    application.run_polling()

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    main()

