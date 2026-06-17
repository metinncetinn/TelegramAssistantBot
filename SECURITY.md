# 🔒 Security & Best Practices

## Yapılan Güvenlik Iyileştirmeleri

### 1. **Credential Management** ✅
- ❌ **Eski**: Hardcoded credentials (botApi.py'de açık token'lar)
- ✅ **Yeni**: Environment variables (.env dosyası)
  ```python
  # ESKI (GÜVENLI DEĞIL)
  TELEGRAM_TOKEN = '8246028848:AAEdIGDFP6i1nGkGG1rt...'
  
  # YENİ (GÜVENLI)
  from dotenv import load_dotenv
  TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
  ```

### 2. **Data Integrity** ✅
- ❌ **Eski**: Doğrudan JSON yazma (crash sırasında veri kayıp riski)
- ✅ **Yeni**: Atomic file operations (temp file → rename)
  ```python
  def save_json(path, data):
      temp_path = path + '.tmp'
      with open(temp_path, 'w') as f:
          json.dump(data, f)
      os.rename(temp_path, path)  # Atomic
  ```

### 3. **Input Validation** ✅
- ❌ **Eski**: Validasyon yok
  ```python
  @app.post('/api/portfolio/add')
  def portfolio_add(req: TxRequest):
      if req.key not in CURRENCY_NAMES: raise HTTPException(400)
      # Negatif, büyük değerler kontrol yok!
  ```

- ✅ **Yeni**: Pydantic validators
  ```python
  class TxRequest(BaseModel):
      key: str
      amount: float
      
      @field_validator('amount')
      def validate_amount(cls, v):
          if v <= 0:
              raise ValueError('Miktar 0\'dan büyük olmalı')
          if v > 999_999_999:
              raise ValueError('Çok büyük değer')
          return v
  ```

### 4. **Error Handling** ✅
- ❌ **Eski**: Bare except, açılı error mesajları
- ✅ **Yeni**: Type-specific exception handling
  ```python
  try:
      # işlem
  except HTTPException:
      raise  # Bilinen hatalar
  except Exception as e:
      raise HTTPException(500, f'Hata: {str(e)}')
  ```

### 5. **API Performance & Rate Limiting** ✅
- ❌ **Eski**: Her istek için yeni API call
- ✅ **Yeni**: Caching + TTL
  ```python
  rate_cache = Cache(ttl_seconds=300)  # 5 min
  
  def get_rates(use_cache=True):
      if use_cache:
          cached = rate_cache.get('rates')
          if cached:
              return cached
  ```

---

## 🛡️ Production Checklist

### Before Deployment to Raspberry Pi

- [ ] `.env` dosyası oluşturuldu ve tüm değerler dolduruldu
- [ ] `.env` dosyası `.gitignore`'da ve hiç commit edilmedi
- [ ] `DEBUG=false` ayarlandı
- [ ] TELEGRAM_TOKEN geçerli ve aktif
- [ ] OPENWEATHER_API_KEY geçerli
- [ ] WOL_MAC_ADDRESS doğru format (AA:BB:CC:DD:EE:FF)
- [ ] `python -m py_compile *.py` hatasız geçti
- [ ] `pip install -r requirements.txt` başarılı
- [ ] `uvicorn main:app` localhost'ta test edildi
- [ ] Systemd service dosyası oluşturuldu
- [ ] Port 8000 açık / firewall kuralı yapılandırıldı
- [ ] Nginx reverse proxy yapılandırıldı (opsiyonel)

### Continuous Operations

```bash
# Daily
sudo systemctl status pi-dashboard

# Weekly
sudo journalctl -u pi-dashboard | tail -100

# Monthly
git pull origin main  # Güncellemeleri çek
pip install -r requirements.txt --upgrade  # Bağımlılık güncellemeleri
```

---

## 🚨 Common Vulnerabilities (Giderildi)

| Zafiyet | Risk | Çözüm |
|---------|------|-------|
| Hardcoded secrets | API abuse, account takeover | .env + .gitignore |
| SQL injection | Database compromise | Pydantic validation |
| Race conditions | Data loss | Atomic file writes |
| Denial of Service | Server crash | Caching + timeout |
| Information leak | Sensitive data exposure | Error message filtering |

---

## 🔐 Environment Variables Best Practices

### Local Development
```bash
# .env dosyası oluştur
cp .env.example .env
nano .env  # Şahsi test token'larını yaz

# Asla version control'e commit etme
git status  # .env görmemeli
```

### Production (Raspberry Pi)
```bash
# Systemd ortamında set et
# /etc/systemd/system/pi-dashboard.service
[Service]
EnvironmentFile=/home/pi/pi-dashboard/.env

# Veya /etc/environment'a yaz (global)
echo "TELEGRAM_TOKEN=..." | sudo tee -a /etc/environment
```

---

## 🔍 Audit & Monitoring

### Log Kontrolü
```bash
# Tüm requests
sudo journalctl -u pi-dashboard -f

# Sadece hatalar
sudo journalctl -u pi-dashboard --grep="ERROR"

# Son 100 satır
sudo journalctl -u pi-dashboard -n 100
```

### Performance Monitoring
```python
# Opsiyonel: Prometheus metrics
from prometheus_client import Counter, Histogram

request_count = Counter('api_requests_total', 'Total API requests', ['endpoint'])
request_duration = Histogram('api_request_duration_seconds', 'API request duration')
```

---

## 📋 Security Headers (Nginx)

```nginx
location / {
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self'" always;
}
```

---

## 🆘 Incident Response

### Eğer Token'ı commit ettiysen (Oops!)

1. **Immediate**:
   ```bash
   # Token'ı Telegram'da rotate et
   # @BotFather → /token → Yeni token al
   ```

2. **Repository**:
   ```bash
   # GitHub'da erişim kontrol
   # Settings → Security → Delete old secrets
   
   # Lokal history'den sil
   git log --oneline | head
   git rebase -i HEAD~<N>  # N: kaç commit geri
   git push --force-with-lease  # Güvenli force push
   ```

3. **Monitoring**:
   - Telegram logs'da alışılmadık aktivite var mı kontrol et
   - API rate limiting'i kontrol et

---

## 📚 Referanslar

- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [Python-dotenv Documentation](https://github.com/theskumar/python-dotenv)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Telegram Bot Security Best Practices](https://core.telegram.org/bots/faq)

---

**Version**: 2.0.0  
**Last Updated**: 2024-06-11  
**Status**: Production Ready ✅
