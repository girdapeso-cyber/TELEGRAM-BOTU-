# Gerekli kütüphaneleri yüklüyoruz.
# Terminal veya komut istemine şunu yazarak yükleyebilirsiniz:
# pip install --upgrade python-telegram-bot
import os
import time
import threading
from threading import active_count
import requests
import urllib
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# --- GÜVENLİ BOT AYARLARI ---
# Hassas bilgiler artık kodun içinde değil, Railway'deki Ortam Değişkenlerinden okunacak.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
AUTHORIZED_USERS_STR = os.environ.get("AUTHORIZED_USERS")
TARGET_CHANNEL_USERNAME = os.environ.get("TARGET_CHANNEL_USERNAME")

# Gelen string'i sayı listesine çeviriyoruz
AUTHORIZED_USERS = [int(user_id.strip()) for user_id in AUTHORIZED_USERS_STR.split(',')] if AUTHORIZED_USERS_STR else []

N_THREADS = 400

# --- OTOMATİK İŞLEM İÇİN GLOBAL DEĞİŞKENLER ---
auto_process_thread = None
stop_event = None

# --- ORİJİNAL KODUNUZUN FONKSİYONLARI ---

def scrap():
    """Proxy'leri online kaynaklardan çeker ve dosyalara yazar."""
    try:
        https = requests.get("https://api.proxyscrape.com/?request=displayproxies&proxytype=https&timeout=0", proxies=urllib.request.getproxies(), timeout=5).text
        http = requests.get("https://api.proxyscrape.com/?request=displayproxies&proxytype=http&timeout=0", proxies=urllib.request.getproxies(), timeout=5).text
        socks = requests.get("https://api.proxyscrape.com/?request=displayproxies&proxytype=socks5&timeout=0", proxies=urllib.request.getproxies(), timeout=5).text
    except Exception as e:
        print(f"Proxy çekme hatası: {e}")
        return False
    with open("proxies.txt", "w", encoding='utf-8') as f:
        f.write(https+"\n"+http)
    with open("socks.txt", "w", encoding='utf-8') as f:
        f.write(socks)
    return True

def send_seen(channel, msgid, proxy):
    """Belirtilen posta bir proxy kullanarak view gönderir."""
    s = requests.Session()
    proxies = {'http': proxy, 'https': proxy}
    try:
        a = s.get(f"https://t.me/{channel}/{msgid}", timeout=10, proxies=proxies)
        cookie = a.headers['set-cookie'].split(';')[0]
        h1 = {"Accept": "*/*", "Connection": "keep-alive", "Content-type": "application/x-www-form-urlencoded",
              "Cookie": cookie, "Host": "t.me", "Origin": "https://t.me", "Referer": f"https://t.me/{channel}/{msgid}?embed=1", "User-Agent": "Chrome"}
        d1 = {"_rl": "1"}
        r = s.post(f'https://t.me/{channel}/{msgid}?embed=1', json=d1, headers=h1, proxies=proxies, timeout=10)
        key = r.text.split('data-view="')[1].split('"')[0]
        h2 = {"Accept": "*/*", "Connection": "keep-alive", "Cookie": cookie, "Host": "t.me",
              "Referer": f"https://t.me/{channel}/{msgid}?embed=1", "User-Agent": "Chrome", "X-Requested-With": "XMLHttpRequest"}
        s.get('https://t.me/v/?views='+key, timeout=10, headers=h2, proxies=proxies)
    except Exception:
        return

def checker(proxy, links, current_stop_event):
    """view gönderme işlemini hata kontrolü ile çalıştırır."""
    if current_stop_event.is_set(): return
    for i in links:
        if current_stop_event.is_set(): break
        try:
            channel = i.split('/')[3]
            msgid = i.split('/')[4]
            send_seen(channel, msgid, proxy)
        except (IndexError, ValueError):
            continue

def run_continuous_process(links, current_stop_event, bot, admin_id):
    """Yeni bir post için durdurulana kadar sürekli izlenme gönderir."""
    while not current_stop_event.is_set():
        print(f"{links[0]} için yeni bir izlenme döngüsü başlıyor...")
        if not scrap():
            print("Proxy'ler çekilemedi, 30 saniye bekleniyor.")
            time.sleep(30)
            continue
        
        threads = []
        try:
            with open('proxies.txt', 'r') as list_file:
                proxies = list_file.readlines()
            for p in proxies:
                if current_stop_event.is_set(): break
                proxy = p.strip()
                if not proxy: continue
                while active_count() > N_THREADS: time.sleep(0.1)
                thread = threading.Thread(target=checker, args=(proxy, links, current_stop_event))
                threads.append(thread)
                thread.start()

            with open('socks.txt', 'r') as list_file:
                proxies = list_file.readlines()
            for p in proxies:
                if current_stop_event.is_set(): break
                proxy = p.strip()
                if not proxy: continue
                while active_count() > N_THREADS: time.sleep(0.1)
                pr = "socks5://" + proxy
                thread = threading.Thread(target=checker, args=(pr, links, current_stop_event))
                threads.append(thread)
                thread.start()
        except FileNotFoundError:
            pass
            
        for thread in threads:
            thread.join()
        
        if current_stop_event.is_set():
            print(f"{links[0]} için işlem durduruldu.")
            break
        
        print("Proxy listesi tamamlandı, 5 saniye sonra yeniden başlıyor...")
        time.sleep(5)
    print("Sürekli işlem döngüsü sonlandı.")


# --- TELEGRAM BOT ENTEGRASYONU ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start komutuna yanıt verir."""
    user = update.effective_user
    if user.id not in AUTHORIZED_USERS:
        return
    await update.message.reply_html(
        f"Merhaba {user.mention_html()}! 👋\n\n"
        f"Bot otomatik modda çalışıyor ve <b>@{TARGET_CHANNEL_USERNAME}</b> kanalını dinliyor."
    )

async def handle_new_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Hedef kanala yeni bir post geldiğinde tetiklenir."""
    global auto_process_thread, stop_event

    post = update.channel_post
    if not post or not post.chat or not TARGET_CHANNEL_USERNAME or post.chat.username != TARGET_CHANNEL_USERNAME:
        return
    
    admin_id = AUTHORIZED_USERS[0] if AUTHORIZED_USERS else None
    if not admin_id: return
    
    if auto_process_thread and auto_process_thread.is_alive():
        print("Önceki izlenme işlemi durduruluyor...")
        try:
            await context.bot.send_message(admin_id, "Yeni gönderi algılandı. Önceki işlem durduruluyor...")
        except Exception as e:
            print(f"Yöneticiye mesaj gönderilemedi: {e}")
            
        if stop_event: stop_event.set()
        auto_process_thread.join(timeout=10)

    new_link = f"https://t.me/{post.chat.username}/{post.message_id}"
    print(f"Yeni işlem başlatılıyor: {new_link}")
    try:
        await context.bot.send_message(admin_id, f"Yeni gönderi için sürekli izlenme işlemi başlatılıyor:\n{new_link}")
    except Exception as e:
        print(f"Yöneticiye mesaj gönderilemedi: {e}")

    stop_event = threading.Event()
    auto_process_thread = threading.Thread(target=run_continuous_process, args=([new_link], stop_event, context.bot, admin_id), daemon=True)
    auto_process_thread.start()


def main() -> None:
    """Botu başlatır ve çalıştırır."""
    if not all([TELEGRAM_BOT_TOKEN, AUTHORIZED_USERS, TARGET_CHANNEL_USERNAME]):
        print("HATA: Lütfen Railway'deki tüm ortam değişkenlerini (TELEGRAM_BOT_TOKEN, AUTHORIZED_USERS, TARGET_CHANNEL_USERNAME) ayarladığınızdan emin olun.")
        return
        
    print("Bot başlatılıyor...")
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, handle_new_channel_post))

    print(f"Bot @{TARGET_CHANNEL_USERNAME} kanalını dinliyor...")
    application.run_polling()

if __name__ == "__main__":
    main()

