# Pi Dashboard — Deployment Guide

## 🚀 Kurulum (Raspberry Pi / Linux)

### 1. Repository'i clone edin
```bash
git clone <repository-url> ~/pi-dashboard
cd ~/pi-dashboard
```

### 2. Environment dosyasını oluşturun
```bash
cp .env.example .env
nano .env  # Veya vim/editor ile açıp değerleri girin
```

**Gerekli değişkenler:**
- `TELEGRAM_TOKEN`: Telegram Bot API token'ınız
- `TELEGRAM_CHAT_ID`: Mesaj göndereceğiniz chat ID'si
- `OPENWEATHER_API_KEY`: openweathermap.org'dan API anahtarı
- `HUGGINGFACE_TOKEN`: huggingface.co'dan token (resim üretimi için)
- `WOL_MAC_ADDRESS`: Uyanması gereken bilgisayarın MAC adresi (xx:xx:xx:xx:xx:xx formatında)

### 3. Python ortamını oluşturun
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. FastAPI sunucusunu başlatın
```bash
# Development (test için)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Production (Systemd ile)
# Aşağıdaki systemd service dosyasını oluşturun
```

## 🔧 Systemd Service (Production)

`/etc/systemd/system/pi-dashboard.service` oluşturun:

```ini
[Unit]
Description=Pi Dashboard Backend
After=network.target

[Service]
Type=notify
User=pi
WorkingDirectory=/home/pi/pi-dashboard
Environment="PATH=/home/pi/pi-dashboard/venv/bin"
ExecStart=/home/pi/pi-dashboard/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Aktif etmek için:
```bash
sudo systemctl daemon-reload
sudo systemctl enable pi-dashboard
sudo systemctl start pi-dashboard

# Status kontrol
sudo systemctl status pi-dashboard
sudo journalctl -u pi-dashboard -f
```

## 📋 Telegram Bot Kurulumu

1. [@BotFather](https://t.me/botfather) ile konuşup `/newbot` komutu verin
2. Bot adını ve username'ini belirleyin
3. Aldığınız token'ı `.env` dosyasına `TELEGRAM_TOKEN` olarak yapıştırın

Chat ID'sini bulmak:
- Bot'a mesaj gönderin: `/start`
- Ardından şu URL'yi tarayıcıda açın: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
- `chat.id` değerini kopyalayıp `.env`'e yapıştırın

## 🌍 Nginx ile Ters Proxy (Opsiyonel)

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket desteği (opsiyonel)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 📱 Web Arayüzüne Erişim

```
http://<raspberry-pi-ip>:8000
```

Yapılandırılmış domain'in olması durumunda:
```
https://your-domain.com
```

## 🔒 Güvenlik

- **Açığa Çıkmış Credentials**: `.env` dosyası **asla** version control'e commit edilmemelidir. `.gitignore` zaten konfigüre edilmiştir.
- **API Caching**: Kur ve hava verisi 5-10 dakikalık cache'de tutulur, API sınırlarını aşmamak için.
- **Input Validation**: Tüm giriş değerleri backend'de kontrol edilir.
- **Rate Limiting**: Web arayüzü 3 dakikada bir portföyü otomatik günceller.

## 🐛 Troubleshooting

### Port 8000 halihazırda kullanımda
```bash
lsof -i :8000  # Hangi process kullanıyor bul
sudo kill -9 <PID>  # Veya farklı port kullan
```

### API hatası: "Kur verisi alınamadı"
- Altinkaynak sunucuları down olabilir
- Internet bağlantısını kontrol edin
- Cache'i temizlemek için sunucuyu yeniden başlatın

### Hava durumu "Hava durumu API anahtarı yapılandırılmadı"
- `.env` dosyasında `OPENWEATHER_API_KEY` kontrol edin
- [openweathermap.org](https://openweathermap.org/api)'den ücretsiz API anahtarı alın

## 📊 Dosya Yapısı

```
pi-dashboard/
├── main.py           # FastAPI backend (ana sunucu)
├── bot.py            # Telegram bot (opsiyonel)
├── botApi.py         # Bot konfigürasyonu
├── index.html        # Web arayüzü
├── .env              # Gizli değişkenler (REPO'DA YOK)
├── .env.example      # Template
├── .gitignore        # Git ignore kuralları
├── requirements.txt  # Python bağımlılıkları
└── README.md         # Proje hakkında
```

## 🔄 Güncellemeleri Çekin

```bash
cd ~/pi-dashboard
git pull origin main
pip install -r requirements.txt  # Yeni bağımlılıklar varsa
sudo systemctl restart pi-dashboard  # Servisi yeniden başlat
```

## 📞 Destek

Sorun yaşarsanız, GitHub'da bir issue açın veya `systemctl status pi-dashboard` loglarını kontrol edin.

---

**Son Güncelleme**: 2024
**Version**: 2.0.0
