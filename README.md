# KRBRZ Network Stress Tester

Telegram Bot tabanlı CDN performans test sistemi. @KRBZ_VIP_TR kanalına yeni içerik düştüğünde, proxy havuzu üzerinden paralel stres testi uygular.

## Kurulum

### Gereksinimler

- Python 3.11+
- Telegram Bot Token ([BotFather](https://t.me/BotFather) üzerinden alınır)

### Adımlar

```bash
# Repo'yu klonla
git clone <repo-url>
cd krbrz-network-stress-tester

# Sanal ortam oluştur
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Bağımlılıkları kur
pip install -r requirements.txt

# Ortam değişkenlerini ayarla
cp .env.example .env
# .env dosyasını düzenle ve değerleri gir
```

### Docker ile Kurulum

```bash
docker build -t krbrz-stress-tester .
docker run --env-file .env krbrz-stress-tester
```

## Yapılandırma

Tüm parametreler `.env` dosyasından veya ortam değişkenlerinden okunur:

| Parametre | Varsayılan | Açıklama |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | *(zorunlu)* | Telegram Bot API token |
| `AUTHORIZED_USERS` | `6699195226` | Yetkili kullanıcı ID'leri (virgülle ayrılmış) |
| `TARGET_CHANNEL` | `KRBZ_VIP_TR` | İzlenecek kanal adı (@ olmadan) |
| `MAX_THREADS` | `400` | Maksimum eşzamanlı thread sayısı |
| `REQUEST_TIMEOUT` | `10` | HTTP istek timeout süresi (saniye) |
| `RETRY_DELAY` | `5` | Hata sonrası yeniden deneme bekleme süresi (saniye) |
| `CYCLE_PAUSE` | `2` | Döngüler arası mola süresi (saniye) |

## Kullanım

### Bot'u Başlatma

```bash
python main.py
```

### Telegram Komutları

- `/start` — Bot durumunu gösterir ve hoş geldin mesajı gönderir

### Çalışma Mantığı

1. Bot, `TARGET_CHANNEL` kanalını sürekli dinler
2. Yeni post tespit edildiğinde, mevcut test döngüsü durdurulur
3. Proxyscrape.com'dan yeni proxy havuzu çekilir
4. 400 eşzamanlı thread ile Telegram görüntülenme protokolü uygulanır
5. Proxy havuzu tükendiğinde yeni havuz çekilip döngü tekrarlanır

## Proje Yapısı

```
├── main.py                  # Giriş noktası
├── config.py                # Yapılandırma yükleyici
├── src/
│   ├── bot_controller.py    # Telegram Bot yönetimi
│   ├── handlers/
│   │   ├── command_handler.py   # /start komutu
│   │   └── event_handler.py     # Kanal post işleme
│   ├── models/
│   │   ├── config.py            # Configuration dataclass
│   │   └── data_models.py       # ProxyInfo, EventInfo, CycleState
│   └── services/
│       ├── notification_service.py   # Kullanıcı bildirimleri
│       ├── process_manager.py        # Test döngüsü yönetimi
│       ├── proxy_scraper.py          # Proxy havuzu çekme
│       ├── request_worker.py         # Tek proxy üzerinden istek
│       ├── stop_event_controller.py  # Stop sinyal yönetimi
│       ├── thread_coordinator.py     # Thread havuzu koordinasyonu
│       └── view_protocol_handler.py  # Telegram view protokolü
├── tests/
│   ├── unit/                # Birim testler
│   └── property/            # Property-based testler (Hypothesis)
├── requirements.txt
├── Dockerfile
└── .env.example
```

## Testler

```bash
# Tüm testler
pytest tests/

# Birim testler
pytest tests/unit/

# Property testler
pytest tests/property/

# Kapsam raporu
pytest --cov=src tests/
```

## Troubleshooting

### Bot başlamıyor
- `TELEGRAM_BOT_TOKEN` değerinin doğru olduğundan emin olun
- İnternet bağlantısını kontrol edin
- `pip install -r requirements.txt` ile bağımlılıkları yeniden kurun

### Proxy çekme başarısız
- Proxyscrape.com erişimini kontrol edin
- Sistem otomatik olarak 5 saniye bekleyip tekrar dener

### Thread'ler yanıt vermiyor
- `MAX_THREADS` değerini düşürmeyi deneyin (örn. 200)
- Sunucu kaynaklarını (CPU, RAM) kontrol edin

### Yetkisiz kullanıcı uyarısı
- `AUTHORIZED_USERS` listesinde Telegram kullanıcı ID'nizin olduğundan emin olun
- ID'yi öğrenmek için [@userinfobot](https://t.me/userinfobot) kullanabilirsiniz

## AWS Deployment

```bash
# Docker image oluştur
docker build -t krbrz-stress-tester .

# ECR'ye push et
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker tag krbrz-stress-tester:latest <account>.dkr.ecr.<region>.amazonaws.com/krbrz-stress-tester:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/krbrz-stress-tester:latest

# ECS veya EC2 üzerinde çalıştır
docker run --env-file .env krbrz-stress-tester
```
