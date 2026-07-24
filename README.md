# 🚀 Pi Dashboard — Professional Edition v2.0

**Web tabanlı finansal dashboard** + Telegram bot entegrasyonu with **Raspberry Pi support**

## ✨ Özellikler

### 📊 Web Arayüzü
- **Portföy Yönetimi** — Döviz (USD, EUR, GBP, JPY) ve altın (gram, çeyrek, yarım, tam) takibi
- **Yatırım Fonları** — TEFAS bağlantısı ile gerçek zamanlı fon fiyatları
- **Hava Durumu** — OpenWeather API entegrasyonu
- **Hatırlatıcılar** — Tek seferlik veya tekrarlayan reminders
- **Resim Üretimi** — Hugging Face FLUX.1 modeli ile AI resim oluşturma
- **Wake-on-LAN** — Bilgisayarı uzaktan açma

### 🤖 Telegram Bot
- Telegram üzerinden portföy sorgulama
- Kur ve altın fiyatı bilgileri
- Otomatik hatırlatıcılar
- Hava durumu bildirimleri

### 🔒 Güvenlik
- ✅ Environment variables ile credential management
- ✅ Pydantic validators ile strict input validation
- ✅ Atomic file operations ile race condition önleme
- ✅ API caching ile DDoS koruma
- ✅ Comprehensive error handling

---

## 🚀 Hızlı Başlangıç

### 1. Repo'yu clone edin
```bash
git clone https://github.com/metinncetinn/TelegramAssistantBot ~/pi-dashboard
cd ~/pi-dashboard
```

### 2. Environment dosyasını oluşturun
```bash
cp .env.example .env
nano .env  # Gerekli değerleri girin
```

**Gerekli değişkenler:**
- `TELEGRAM_TOKEN` (Telegram Bot API)
- `OPENWEATHER_API_KEY` (openweathermap.org)
- `HUGGINGFACE_TOKEN` (Resim üretimi için - opsiyonel)
- `WOL_MAC_ADDRESS` (Bilgisayarın MAC adresi - opsiyonel)

### 3. Python ortamını kurun
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Sunucuyu başlatın
```bash
# Development
uvicorn main:app --host 0.0.0.0 --port 8000

# Veya tarayıcıda açın: http://localhost:8000
```

---

## 📚 Dokumentasyon

- **[QUICKSTART.md](QUICKSTART.md)** — 5 dakikada başlama rehberi
- **[DEPLOYMENT.md](DEPLOYMENT.md)** — Raspberry Pi'de production kurulumu
- **[SECURITY.md](SECURITY.md)** — Güvenlik best practices ve audit

---

## 📁 Proje Yapısı

```
pi-dashboard/
├── main.py              # FastAPI backend (ana sunucu)
├── bot.py               # Telegram bot (opsiyonel)
├── botApi.py            # Bot konfigürasyonu
├── index.html           # Web arayüzü (SPA)
│
├── .env                 # Credentials (GIT'E COMMIT ETMEYİN)
├── .env.example         # Template
├── .gitignore          # Git ignore kuralları
├── requirements.txt    # Python bağımlılıkları
│
├── QUICKSTART.md       # Başlama rehberi
├── DEPLOYMENT.md       # Production kurulumu
├── SECURITY.md         # Güvenlik rehberi
└── README.md           # Bu dosya
```

---

## 🛠 Teknoloji Stack

| Bileşen | Teknoloji |
|---------|-----------|
| **Backend** | FastAPI + Uvicorn |
| **Frontend** | Vanilla HTML/CSS/JS |
| **Bot** | python-telegram-bot |
| **Database** | JSON + Atomic operations |
| **APIs** | Altinkaynak, OpenWeather, TEFAS, HuggingFace |
| **Deployment** | Systemd (Linux/RPi) |

---

## 📊 API Endpoints

### Portfolio
- `GET /api/portfolio` — Portföy özeti
- `POST /api/portfolio/add` — Kripto/döviz ekle
- `POST /api/portfolio/remove` — Kripto/döviz çıkar

### Funds
- `GET /api/funds` — Yatırım fonları
- `POST /api/funds` — Fon ekle
- `DELETE /api/funds/{kod}` — Fon sil

### Weather
- `GET /api/weather` — Hava durumu

### Tools
- `POST /api/wol` — Wake-on-LAN
- `POST /api/generate-image` — AI resim üretimi

### System
- `GET /api/health` — Sunucu durumu
- `GET /api/config` — Konfigürasyon

---

## 🔄 v2.0 Değişiklikleri (Professional Edition)

### Güvenlik
- ✅ Hardcoded token'lar kaldırıldı → .env sistemi
- ✅ Input validation eklendi (Pydantic)
- ✅ Error handling iyileştirildi
- ✅ Atomic file writes (race condition fix)

### Performance
- ✅ API Caching (kur: 5 min, hava: 10 min)
- ✅ Request timeout (15 sec)
- ✅ Floating point rounding (2 decimal)

### DevOps
- ✅ Systemd service template
- ✅ Production deployment guide
- ✅ Security best practices doc
- ✅ Comprehensive error messages

---

## 🐛 Troubleshooting

### Port 8000 Zaten Kullanımda
```bash
lsof -i :8000
sudo kill -9 <PID>
# Veya farklı port: uvicorn main:app --port 8001
```

### API Hatası: "Kur verisi alınamadı"
```bash
# Cache'i temizle
sudo systemctl restart pi-dashboard
# Veya internet bağlantısını kontrol et
```

### Telegram Bot Yanıt Vermiyor
```bash
# Token'ı kontrol et
curl https://api.telegram.org/bot<TOKEN>/getMe

# Logs'u kontrol et
sudo journalctl -u pi-dashboard -f
```

---

## 📞 Destek

- 🐛 **Bug Report**: GitHub Issues
- 💡 **Feature Request**: GitHub Discussions
- 🔒 **Security Issue**: GitHub Security Advisories

---

## 📄 Lisans

MIT License — Özgürce kullanabilirsiniz

---

## 👤 Yapımcı

**Metin Çetinn** (@metinncetinn)

---

## 🔗 İlişkili Projektler

- [TEFAS API](https://www.tefas.gov.tr/)
- [Altinkaynak API](https://www.altinkaynak.com/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [FastAPI Framework](https://fastapi.tiangolo.com/)

---

**Version**: 2.0.0 (Professional Edition)  
**Last Updated**: 2024-06-11  
**Status**: Production Ready ✅
