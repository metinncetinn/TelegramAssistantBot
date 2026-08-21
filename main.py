"""
Pi Dashboard — FastAPI Backend (Professional Edition v2.0)
Çalıştırma: uvicorn main:app --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
import json, os, datetime, uuid, requests, pytz, time, threading, hashlib, shutil, subprocess, mimetypes
import numpy as np
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Pi Dashboard API", version="2.0.0")

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
DATA_FILE      = os.path.join(BASE_DIR, 'wallet.json')
FUNDS_FILE     = os.path.join(BASE_DIR, 'funds.json')
REMINDERS_FILE = os.path.join(BASE_DIR, 'reminders.json')

OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '')
LOCATION            = os.getenv('LOCATION', 'Konya')
WOL_MAC_ADDRESS     = os.getenv('WOL_MAC_ADDRESS', '')
HUGGINGFACE_TOKEN   = os.getenv('HUGGINGFACE_TOKEN', '')

GALLERY_DIR = os.getenv('GALLERY_DIR', '/mnt/ssd/gallery')
THUMB_DIR   = os.path.join(BASE_DIR, 'gallery_thumbs')

VAPID_PRIVATE_KEY_FILE = os.path.join(BASE_DIR, 'vapid_private.pem')
VAPID_PUBLIC_KEY_FILE  = os.path.join(BASE_DIR, 'vapid_public.pem')
VAPID_EMAIL            = os.getenv('VAPID_EMAIL', 'mailto:admin@pidashboard.local')
SUBSCRIPTIONS_FILE     = os.path.join(BASE_DIR, 'subscriptions.json')

VAPID_PUBLIC_KEY_B64 = None
try:
    from py_vapid import Vapid as _Vapid
    from cryptography.hazmat.primitives.serialization import Encoding as _Enc, PublicFormat as _PF
    import base64 as _b64
    if os.path.exists(VAPID_PRIVATE_KEY_FILE):
        _v = _Vapid.from_file(VAPID_PRIVATE_KEY_FILE)
        _raw = _v.public_key.public_bytes(_Enc.X962, _PF.UncompressedPoint)
        VAPID_PUBLIC_KEY_B64 = _b64.urlsafe_b64encode(_raw).rstrip(b'=').decode()
        print(f"✓ VAPID hazır: {VAPID_PUBLIC_KEY_B64[:20]}...")
except Exception as _e:
    print(f"⚠ VAPID init hatası: {_e}")

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif', '.gif', '.bmp'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.3gp', '.webm', '.m4v'}
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

ALTINKAYNAK_GOLD_URL     = 'https://static.altinkaynak.com/public/Gold'
ALTINKAYNAK_CURRENCY_URL = 'https://static.altinkaynak.com/public/Currency'

CURRENCY_NAMES = {
    'usd': 'Dolar', 'eur': 'Euro', 'gbp': 'Sterlin', 'jpy': 'Japon Yeni',
    'gram': 'Gram Altın', 'ceyrek': 'Çeyrek Altın',
    'yarim': 'Yarım Altın', 'tam': 'Tam Altın'
}
CURRENCY_SYMBOLS = {
    'usd': '$', 'eur': '€', 'gbp': '£', 'jpy': '¥',
    'gram': 'gr', 'ceyrek': '¼', 'yarim': '½', 'tam': '1'
}

TZ = pytz.timezone('Europe/Istanbul')


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# YARDIMCI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def parse_tr(v: str) -> float:
    try: return float(v.replace('.', '').replace(',', '.'))
    except: return 0.0

def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except: pass
    return default

def save_json(path, data):
    try:
        temp_path = path + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if os.path.exists(path):
            os.remove(path)
        os.rename(temp_path, path)
    except Exception as e:
        print(f"JSON yazma hatası ({path}): {e}")
        raise HTTPException(500, f"Veri kaydetme hatası: {str(e)}")

def load_wallet():
    data = load_json(DATA_FILE, {})
    for k in CURRENCY_NAMES:
        if k not in data:
            data[k] = {'amount': 0.0, 'cost': 0.0}
        elif isinstance(data[k], (int, float)):
            data[k] = {'amount': float(data[k]), 'cost': 0.0}
    return data

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CACHE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Cache:
    def __init__(self, ttl_seconds=300):
        self.data = {}
        self.ttl = ttl_seconds
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            if key in self.data:
                value, timestamp = self.data[key]
                if time.time() - timestamp < self.ttl:
                    return value
                del self.data[key]
        return None

    def set(self, key, value):
        with self.lock:
            self.data[key] = (value, time.time())

    def invalidate(self, key):
        with self.lock:
            self.data.pop(key, None)

rate_cache    = Cache(ttl_seconds=300)
weather_cache = Cache(ttl_seconds=600)
gallery_cache = Cache(ttl_seconds=30)
funds_cache   = Cache(ttl_seconds=900)  # 15 dakika — TEFAS günde 1 kez güncellenir

def get_rates(use_cache=True):
    if use_cache:
        cached = rate_cache.get('rates')
        if cached:
            return cached
    rates = {}
    try:
        r = requests.get(ALTINKAYNAK_CURRENCY_URL, timeout=10)
        if r.ok:
            for item in r.json():
                k, v = item.get('Kod', '').upper(), item.get('Alis', '0')
                if k == 'USD':   rates['usd'] = parse_tr(v)
                elif k == 'EUR': rates['eur'] = parse_tr(v)
                elif k == 'GBP': rates['gbp'] = parse_tr(v)
                elif k == 'JPY': rates['jpy'] = parse_tr(v)
    except: pass
    try:
        r = requests.get(ALTINKAYNAK_GOLD_URL, timeout=10)
        if r.ok:
            for item in r.json():
                k, v = item.get('Kod', '').upper(), item.get('Alis', '0')
                if k == 'PGA':  rates['gram']   = parse_tr(v)
                elif k == 'PC': rates['ceyrek'] = parse_tr(v)
                elif k == 'PY': rates['yarim']  = parse_tr(v)
                elif k == 'PT': rates['tam']    = parse_tr(v)
    except: pass
    if len(rates) >= 6:
        rate_cache.set('rates', rates)
        return rates
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API — PORTFÖy
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get('/api/portfolio')
def portfolio():
    wallet = load_wallet()
    rates  = get_rates()
    if not rates: raise HTTPException(502, 'Kur verisi alınamadı')
    items = []; total_value = total_cost = 0.0
    for key, name in CURRENCY_NAMES.items():
        e = wallet.get(key, {'amount': 0.0, 'cost': 0.0})
        amt, cost = e['amount'], e['cost']
        if amt <= 0: continue
        rate  = rates.get(key, 0)
        value = amt * rate
        pnl   = value - cost
        total_value += value; total_cost += cost
        items.append({
            'key': key, 'name': name, 'symbol': CURRENCY_SYMBOLS[key],
            'amount': amt, 'rate': rate,
            'avg_rate': (cost / amt) if amt else 0,
            'value': value, 'cost': cost,
            'pnl': pnl, 'pnl_pct': (pnl / cost * 100) if cost else 0,
        })
    total_pnl = total_value - total_cost
    return {
        'items': items,
        'total_value': total_value, 'total_cost': total_cost,
        'total_pnl': total_pnl,
        'total_pnl_pct': (total_pnl / total_cost * 100) if total_cost else 0,
        'rates': rates,
        'updated_at': datetime.datetime.now(TZ).strftime('%H:%M:%S'),
    }

class TxRequest(BaseModel):
    key: str
    amount: float

    @field_validator('key')
    @classmethod
    def validate_key(cls, v):
        if v not in CURRENCY_NAMES:
            raise ValueError(f'Geçersiz birim: {v}')
        return v

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Miktar 0\'dan büyük olmalı')
        if v > 999_999_999:
            raise ValueError('Çok büyük değer')
        return v

@app.post('/api/portfolio/add')
def portfolio_add(req: TxRequest):
    try:
        rates = get_rates(use_cache=False)
        if not rates:
            raise HTTPException(502, 'Kur alınamadı')
        rate = rates[req.key]
        cost = req.amount * rate
        w = load_wallet()
        w[req.key]['amount'] = float(w[req.key]['amount']) + req.amount
        w[req.key]['cost']   = float(w[req.key]['cost'])   + cost
        save_json(DATA_FILE, w)
        return {'ok': True, 'rate': round(rate, 2), 'cost': round(cost, 2)}
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, f'Ekleme hatası: {str(e)}')

@app.post('/api/portfolio/remove')
def portfolio_remove(req: TxRequest):
    try:
        w = load_wallet()
        cur = float(w[req.key]['amount'])
        if cur < req.amount: raise HTTPException(400, f'Yetersiz bakiye: {cur:.2f}')
        if cur == 0: raise HTTPException(400, 'Bakiye sıfır')
        ratio = req.amount / cur
        w[req.key]['amount'] -= req.amount
        w[req.key]['cost']   -= float(w[req.key]['cost']) * ratio
        save_json(DATA_FILE, w)
        return {'ok': True}
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, f'Çıkarma hatası: {str(e)}')


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API — YATIRIM FONLARI (TEFAS)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def load_funds():
    return load_json(FUNDS_FILE, {})

def get_tefas_prices():
    """TEFAS'tan tüm fonların güncel fiyatlarını çeker (15dk cache).
    Hafta sonu/tatilde veri yoksa geriye doğru 5 güne kadar dener."""
    cached = funds_cache.get('prices')
    if cached:
        return cached
    try:
        from pytefas import Crawler
    except ImportError:
        raise HTTPException(500, 'pytefas kurulu değil — pip install pytefas --break-system-packages')

    tefas = Crawler()
    for i in range(6):
        day = (datetime.datetime.now(TZ) - datetime.timedelta(days=i)).strftime('%Y-%m-%d')
        try:
            df = tefas.fetch_many(day, columns='info')
            if df is not None and len(df) > 0:
                prices = {}
                for _, row in df.iterrows():
                    prices[row['fund_code']] = {
                        'name': row['fund_name'],
                        'price': float(row['price']),
                        'date': day,
                    }
                funds_cache.set('prices', prices)
                return prices
        except Exception:
            continue
    raise HTTPException(502, 'TEFAS verisi alınamadı')


@app.get('/api/funds')
def funds_list():
    funds  = load_funds()
    prices = get_tefas_prices()
    items = []
    total_value = total_cost = 0.0
    for code, e in funds.items():
        amt, cost = e.get('amount', 0), e.get('cost', 0)
        if amt <= 0: continue
        info  = prices.get(code)
        price = info['price'] if info else 0
        name  = info['name']  if info else code
        value = amt * price
        pnl   = value - cost
        total_value += value; total_cost += cost
        items.append({
            'code': code, 'name': name,
            'amount': amt, 'price': price,
            'avg_cost': (cost / amt) if amt else 0,
            'value': value, 'cost': cost,
            'pnl': pnl, 'pnl_pct': (pnl / cost * 100) if cost else 0,
        })
    total_pnl = total_value - total_cost
    return {
        'items': items,
        'total_value': total_value, 'total_cost': total_cost,
        'total_pnl': total_pnl,
        'total_pnl_pct': (total_pnl / total_cost * 100) if total_cost else 0,
    }


class FundTxRequest(BaseModel):
    code: str
    amount: float

    @field_validator('code')
    @classmethod
    def validate_code(cls, v):
        v = v.strip().upper()
        if not v: raise ValueError('Fon kodu boş olamaz')
        return v

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        if v <= 0: raise ValueError('Miktar 0\'dan büyük olmalı')
        return v


@app.post('/api/funds/add')
def funds_add(req: FundTxRequest):
    try:
        prices = get_tefas_prices()
        info = prices.get(req.code)
        if not info:
            raise HTTPException(404, f'Fon kodu bulunamadı: {req.code}')
        price = info['price']
        cost  = req.amount * price

        funds = load_funds()
        if req.code not in funds:
            funds[req.code] = {'amount': 0.0, 'cost': 0.0}
        funds[req.code]['amount'] += req.amount
        funds[req.code]['cost']   += cost
        save_json(FUNDS_FILE, funds)

        return {'ok': True, 'price': round(price, 4), 'cost': round(cost, 2), 'name': info['name']}
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, f'Ekleme hatası: {str(e)}')


@app.post('/api/funds/remove')
def funds_remove(req: FundTxRequest):
    try:
        funds = load_funds()
        if req.code not in funds:
            raise HTTPException(404, 'Bu fon portföyünüzde yok')
        cur = float(funds[req.code]['amount'])
        if cur < req.amount: raise HTTPException(400, f'Yetersiz adet: {cur:.4f}')
        if cur == 0: raise HTTPException(400, 'Adet sıfır')
        ratio = req.amount / cur
        funds[req.code]['amount'] -= req.amount
        funds[req.code]['cost']   -= float(funds[req.code]['cost']) * ratio
        save_json(FUNDS_FILE, funds)
        return {'ok': True}
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, f'Çıkarma hatası: {str(e)}')


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API — HATIRLATICILAR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get('/api/reminders')
def get_reminders():
    reminders = load_json(REMINDERS_FILE, [])
    now = datetime.datetime.now(TZ)
    out = []
    for r in reminders:
        item = dict(r); item['id_short'] = r['id'][:6]
        if r['type'] == 'once':
            fire = datetime.datetime.fromisoformat(r['fire_at'])
            if fire.tzinfo is None: fire = TZ.localize(fire)
            item['fire_str'] = fire.strftime('%d.%m.%Y %H:%M')
            item['is_past']  = fire < now
        out.append(item)
    return out

class ReminderReq(BaseModel):
    type: str; text: str
    fire_at: str = ''
    repeat_type: str = ''
    weekday: int = -1
    hour: int = 0; minute: int = 0

@app.post('/api/reminders')
def create_reminder(req: ReminderReq):
    now = datetime.datetime.now(TZ)
    r = {'id': str(uuid.uuid4()), 'text': req.text}
    if req.type == 'once':
        fire = None; t = req.fire_at.lower().strip()
        for sfx in ['saat', 's']:
            if t.endswith(sfx):
                try: fire = now + datetime.timedelta(hours=float(t.replace(sfx, ''))); break
                except: pass
        if not fire:
            for sfx in ['dakika', 'dk', 'min', 'm']:
                if t.endswith(sfx):
                    try: fire = now + datetime.timedelta(minutes=float(t.replace(sfx, ''))); break
                    except: pass
        if not fire:
            try:
                h, m = map(int, t.split(':'))
                fire = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if fire <= now: fire += datetime.timedelta(days=1)
            except: pass
        if not fire: raise HTTPException(400, 'Geçersiz zaman formatı')
        r['type'] = 'once'; r['fire_at'] = fire.isoformat()
    elif req.type == 'repeat':
        days = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
        day_str = days[req.weekday] if 0 <= req.weekday <= 6 else ''
        label = f"Her {'gün' if req.repeat_type == 'gün' else 'hafta ' + day_str} {req.hour:02d}:{req.minute:02d}"
        r.update({'type': 'repeat', 'repeat_type': req.repeat_type,
                  'weekday': req.weekday if req.weekday >= 0 else None,
                  'hour': req.hour, 'minute': req.minute, 'repeat_label': label})
    else:
        raise HTTPException(400, 'Geçersiz tip')
    reminders = load_json(REMINDERS_FILE, [])
    reminders.append(r)
    save_json(REMINDERS_FILE, reminders)
    return {'ok': True, 'id': r['id'][:6]}

@app.delete('/api/reminders/{rid}')
def delete_reminder(rid: str):
    reminders = load_json(REMINDERS_FILE, [])
    new = [r for r in reminders if not r['id'].startswith(rid)]
    if len(new) == len(reminders): raise HTTPException(404, 'Bulunamadı')
    save_json(REMINDERS_FILE, new)
    return {'ok': True}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API — HAVA DURUMU
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get('/api/weather')
def weather(city: str = ''):
    try:
        location = city if city else LOCATION
        cache_key = f'weather_{location}'
        cached = weather_cache.get(cache_key)
        if cached: return cached
        if not OPENWEATHER_API_KEY:
            raise HTTPException(400, 'Hava durumu API anahtarı yapılandırılmadı')
        url = f'https://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHER_API_KEY}&units=metric&lang=tr'
        r = requests.get(url, timeout=10)
        if not r.ok: raise HTTPException(r.status_code, f'Konum bulunamadı: {location}')
        d = r.json()
        url2 = f'https://api.openweathermap.org/data/2.5/forecast?q={location}&appid={OPENWEATHER_API_KEY}&units=metric&lang=tr&cnt=1'
        r2 = requests.get(url2, timeout=10)
        pop = 0
        if r2.ok:
            f2 = r2.json()
            if f2.get('list'):
                pop = round(f2['list'][0].get('pop', 0) * 100)
        result = {
            'city': d['name'],
            'temp': round(d['main']['temp']),
            'feels_like': round(d['main']['feels_like']),
            'humidity': d['main']['humidity'],
            'desc': d['weather'][0]['description'].capitalize(),
            'icon': d['weather'][0]['icon'],
            'wind': round(d['wind']['speed'] * 3.6, 1),
            'rain_pct': pop,
        }
        weather_cache.set(cache_key, result)
        return result
    except HTTPException: raise
    except Exception as e: raise HTTPException(502, f'Hava durumu hatası: {str(e)}')


@app.get('/api/weather/forecast')
def weather_forecast(city: str = ''):
    try:
        location = city if city else LOCATION
        cache_key = f'forecast_{location}'
        cached = weather_cache.get(cache_key)
        if cached: return cached
        if not OPENWEATHER_API_KEY:
            raise HTTPException(400, 'API anahtarı yapılandırılmadı')
        url = f'https://api.openweathermap.org/data/2.5/forecast?q={location}&appid={OPENWEATHER_API_KEY}&units=metric&lang=tr&cnt=40'
        r = requests.get(url, timeout=10)
        if not r.ok: raise HTTPException(r.status_code, f'Konum bulunamadı: {location}')
        d = r.json()
        from collections import defaultdict
        days = defaultdict(list)
        for item in d['list']:
            date = item['dt_txt'].split(' ')[0]
            days[date].append(item)
        result = []
        for date, items in sorted(days.items()):
            morning = next((x for x in items if '09:00' in x['dt_txt']), None)
            evening = next((x for x in items if '21:00' in x['dt_txt']), None)
            main_item = morning or evening or items[0]
            temps = [x['main']['temp'] for x in items]
            rain_pcts = [x.get('pop', 0) for x in items]
            result.append({
                'date': date,
                'min_temp': round(min(temps)),
                'max_temp': round(max(temps)),
                'rain_pct': round(max(rain_pcts) * 100),
                'icon': main_item['weather'][0]['icon'],
                'desc': main_item['weather'][0]['description'].capitalize(),
                'morning': {
                    'temp': round(morning['main']['temp']) if morning else None,
                    'icon': morning['weather'][0]['icon'] if morning else None,
                    'desc': morning['weather'][0]['description'].capitalize() if morning else None,
                } if morning else None,
                'evening': {
                    'temp': round(evening['main']['temp']) if evening else None,
                    'icon': evening['weather'][0]['icon'] if evening else None,
                    'desc': evening['weather'][0]['description'].capitalize() if evening else None,
                } if evening else None,
            })
        weather_cache.set(cache_key, result)
        return result
    except HTTPException: raise
    except Exception as e: raise HTTPException(502, f'Tahmin hatası: {str(e)}')


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API — WAKE ON LAN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.post('/api/wol')
def wake_on_lan():
    if not WOL_MAC_ADDRESS:
        raise HTTPException(500, 'WOL_MAC_ADDRESS tanımlı değil')
    try:
        import socket
        mac = WOL_MAC_ADDRESS.replace(':', '').replace('-', '').replace('.', '')
        if len(mac) != 12: raise ValueError('Geçersiz MAC')
        magic = b'\xff' * 6 + bytes.fromhex(mac) * 16
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic, ('255.255.255.255', 9))
        sock.close()
        return {'ok': True, 'mac': WOL_MAC_ADDRESS}
    except Exception as e:
        raise HTTPException(500, str(e))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API — GÖRSEL ÜRETME
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ImageReq(BaseModel):
    prompt: str
    size: str = '1024x1024'

@app.post('/api/generate-image')
def generate_image(req: ImageReq):
    try:
        width, height = 1024, 1024
        if 'x' in req.size:
            parts = req.size.split('x')
            try:
                width  = int(parts[0])
                height = int(parts[1])
            except: pass

        GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

        # Google Gemini (Nano Banana) — kart gerektirmez, günlük ücretsiz kota
        if GEMINI_API_KEY:
            r = requests.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={GEMINI_API_KEY}',
                headers={'Content-Type': 'application/json'},
                json={
                    'contents': [{'parts': [{'text': req.prompt}]}],
                },
                timeout=60
            )
            if r.ok:
                data = r.json()
                try:
                    parts = data['candidates'][0]['content']['parts']
                    for p in parts:
                        if 'inlineData' in p:
                            return {'ok': True, 'image': p['inlineData']['data']}
                    raise HTTPException(500, 'Gemini resim döndürmedi')
                except (KeyError, IndexError):
                    raise HTTPException(500, f'Gemini yanıt hatası: {str(data)[:200]}')
            else:
                # Gemini başarısız olursa Pollinations'a düş
                pass

        # Fallback: Pollinations.ai (API key gerektirmez)
        import urllib.parse
        encoded = urllib.parse.quote(req.prompt)
        url = f'https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true&enhance=true'
        r2 = requests.get(url, timeout=120)
        r2.raise_for_status()
        if not r2.content or len(r2.content) < 100:
            raise HTTPException(500, 'Boş yanıt döndü')
        import base64
        return {'ok': True, 'image': base64.b64encode(r2.content).decode()}

    except HTTPException: raise
    except Exception as e: raise HTTPException(500, str(e))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API — SİSTEM BİLGİSİ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get('/api/system')
def system_info():
    try:
        import psutil
        cpu  = psutil.cpu_percent(interval=0.5)
        ram  = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        try:
            with open('/sys/class/thermal/thermal_zone0/temp') as f:
                temp = int(f.read()) / 1000.0
        except: temp = None
        return {
            'cpu': cpu,
            'ram_pct': ram.percent,
            'ram_used': round(ram.used / 1024**3, 1),
            'ram_total': round(ram.total / 1024**3, 1),
            'disk_pct': disk.percent,
            'disk_used': round(disk.used / 1024**3, 1),
            'disk_total': round(disk.total / 1024**3, 1),
            'temp': temp,
        }
    except ImportError: raise HTTPException(500, 'psutil kurulu değil')


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API — GALERİ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def scan_gallery():
    cached = gallery_cache.get('index')
    if cached: return cached
    items = []
    if os.path.isdir(GALLERY_DIR):
        for root, dirs, files in os.walk(GALLERY_DIR):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for fn in files:
                if fn.startswith('.'): continue
                ext = os.path.splitext(fn)[1].lower()
                if ext not in MEDIA_EXTS: continue
                full = os.path.join(root, fn)
                rel  = os.path.relpath(full, GALLERY_DIR)
                try: stat = os.stat(full)
                except OSError: continue
                gid = hashlib.md5(rel.encode('utf-8')).hexdigest()[:16]
                items.append({
                    'id': gid, 'rel': rel, 'name': fn,
                    'type': 'video' if ext in VIDEO_EXTS else 'image',
                    'size': stat.st_size, 'mtime': stat.st_mtime,
                })
    items.sort(key=lambda x: x['mtime'], reverse=True)
    index = {it['id']: it for it in items}
    result = {'items': items, 'index': index}
    gallery_cache.set('index', result)
    return result


def get_gallery_item(gid: str):
    data = scan_gallery()
    item = data['index'].get(gid)
    if not item: raise HTTPException(404, 'Dosya bulunamadı')
    full = os.path.join(GALLERY_DIR, item['rel'])
    if not os.path.isfile(full): raise HTTPException(404, 'Dosya bulunamadı')
    return item, full


@app.get('/api/gallery')
def gallery_list(page: int = 1, limit: int = 30, type: str = 'all',
                 refresh: bool = False, sort: str = 'date_desc'):
    if refresh: gallery_cache.invalidate('index')
    if page < 1: page = 1
    if limit < 1: limit = 1
    if limit > 100: limit = 100
    data  = scan_gallery()
    items = list(data['items'])
    if type in ('image', 'video'):
        items = [it for it in items if it['type'] == type]
    sort_map = {
        'date_desc': (lambda x: x['mtime'], True),
        'date_asc':  (lambda x: x['mtime'], False),
        'name_asc':  (lambda x: x['name'].lower(), False),
        'name_desc': (lambda x: x['name'].lower(), True),
        'size_desc': (lambda x: x['size'], True),
        'size_asc':  (lambda x: x['size'], False),
    }
    key_fn, reverse = sort_map.get(sort, sort_map['date_desc'])
    items.sort(key=key_fn, reverse=reverse)
    total = len(items)
    pages = max(1, (total + limit - 1) // limit)
    start = (page - 1) * limit
    out = []
    for it in items[start:start + limit]:
        dt = datetime.datetime.fromtimestamp(it['mtime'], TZ)
        out.append({
            'id': it['id'], 'type': it['type'], 'name': it['name'],
            'size': it['size'], 'date': dt.strftime('%d.%m.%Y %H:%M'),
        })
    return {'items': out, 'total': total, 'page': page, 'pages': pages}


@app.get('/api/gallery/thumb/{gid}')
def gallery_thumb(gid: str):
    item, full = get_gallery_item(gid)
    os.makedirs(THUMB_DIR, exist_ok=True)
    thumb_path = os.path.join(THUMB_DIR, gid + '.jpg')
    if not os.path.exists(thumb_path) or os.path.getmtime(thumb_path) < os.path.getmtime(full):
        try:
            if item['type'] == 'image':
                from PIL import Image
                img = Image.open(full).convert('RGB')
                img.thumbnail((480, 480))
                img.save(thumb_path, 'JPEG', quality=82)
            else:
                subprocess.run(
                    ['ffmpeg', '-y', '-ss', '00:00:01', '-i', full,
                     '-frames:v', '1', '-vf', 'scale=480:-2', thumb_path],
                    check=True, capture_output=True, timeout=30,
                )
        except FileNotFoundError:
            raise HTTPException(500, 'ffmpeg kurulu değil')
        except Exception as e:
            raise HTTPException(500, f'Önizleme oluşturulamadı: {e}')
    if not os.path.exists(thumb_path):
        raise HTTPException(500, 'Önizleme oluşturulamadı')
    return FileResponse(thumb_path, media_type='image/jpeg')


@app.get('/api/gallery/file/{gid}')
def gallery_file(gid: str):
    item, full = get_gallery_item(gid)
    ext = os.path.splitext(full)[1].lower()
    if ext in {'.heic', '.heif'}:
        try:
            from PIL import Image
            import io
            img = Image.open(full).convert('RGB')
            buf = io.BytesIO()
            img.save(buf, 'JPEG', quality=92)
            buf.seek(0)
            from fastapi.responses import StreamingResponse
            return StreamingResponse(buf, media_type='image/jpeg')
        except Exception as e:
            raise HTTPException(500, f'HEIC dönüştürme hatası: {e}')
    media_type = mimetypes.guess_type(full)[0] or 'application/octet-stream'
    return FileResponse(full, media_type=media_type)


@app.get('/api/gallery/download/{gid}')
def gallery_download(gid: str):
    item, full = get_gallery_item(gid)
    media_type = mimetypes.guess_type(full)[0] or 'application/octet-stream'
    return FileResponse(full, media_type=media_type, filename=item['name'])


@app.post('/api/gallery/upload')
async def gallery_upload(files: list[UploadFile]):
    if not os.path.isdir(GALLERY_DIR):
        raise HTTPException(500, f'Galeri klasörü bulunamadı: {GALLERY_DIR}')
    results = []
    for file in files:
        try:
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in MEDIA_EXTS:
                results.append({'name': file.filename, 'ok': False, 'error': 'Desteklenmeyen format'})
                continue
            now = datetime.datetime.now(TZ)
            sub_dir = os.path.join(GALLERY_DIR, str(now.year), f'{now.month:02d}')
            os.makedirs(sub_dir, exist_ok=True)
            save_path = os.path.join(sub_dir, file.filename)
            if os.path.exists(save_path):
                name, ext2 = os.path.splitext(file.filename)
                save_path = os.path.join(sub_dir, f'{name}_{int(now.timestamp())}{ext2}')
            content = await file.read()
            with open(save_path, 'wb') as f:
                f.write(content)
            gallery_cache.invalidate('index')
            results.append({'name': file.filename, 'ok': True})
        except Exception as e:
            results.append({'name': file.filename, 'ok': False, 'error': str(e)})
    return {'results': results, 'uploaded': sum(1 for r in results if r['ok'])}


@app.delete('/api/gallery/{gid}')
def gallery_delete(gid: str):
    item, full = get_gallery_item(gid)
    try: os.remove(full)
    except OSError as e: raise HTTPException(500, f'Silme hatası: {e}')
    thumb_path = os.path.join(THUMB_DIR, gid + '.jpg')
    if os.path.exists(thumb_path):
        try: os.remove(thumb_path)
        except OSError: pass
    gallery_cache.invalidate('index')
    return {'ok': True}


@app.get('/api/gallery/storage')
def gallery_storage():
    if not os.path.isdir(GALLERY_DIR):
        raise HTTPException(404, f'Galeri klasörü bulunamadı: {GALLERY_DIR}')
    total, used, free = shutil.disk_usage(GALLERY_DIR)
    data = scan_gallery()
    return {
        'total_gb': round(total / 1024**3, 1),
        'used_gb':  round(used  / 1024**3, 1),
        'free_gb':  round(free  / 1024**3, 1),
        'used_pct': round(used / total * 100, 1) if total else 0,
        'file_count': len(data['items']),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API — YÜZ TANIMA / KİŞİ GRUPLAMA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FACES_FILE           = os.path.join(BASE_DIR, 'faces.json')
FACE_THUMB_DIR       = os.path.join(BASE_DIR, 'face_thumbs')
FACE_MATCH_THRESHOLD = 0.55   # düşük = daha katı eşleştirme (daha az yanlış birleştirme)
FACE_SCAN_MAX_DIM    = 1200   # yüz taraması için resmi bu boyuta küçült (Pi'de hız için)
FACE_BATCH_SIZE      = 15     # her tarama döngüsünde işlenecek maksimum yeni fotoğraf
FACE_SCAN_INTERVAL   = 30     # saniye — yeni fotoğraf bu aralıkla kontrol edilir

faces_lock = threading.Lock()

def load_faces_db():
    return load_json(FACES_FILE, {'processed': {}, 'faces': {}, 'people': {}})

def save_faces_db(db):
    save_json(FACES_FILE, db)

def _face_distance(a, b):
    return float(np.linalg.norm(np.array(a) - np.array(b)))

def _find_best_person(encoding, people):
    """Verilen yüz encoding'ine en yakın kişiyi bulur (eşik altındaysa)."""
    best_pid, best_dist = None, None
    for pid, p in people.items():
        if not p.get('centroid'): continue
        dist = _face_distance(p['centroid'], encoding)
        if best_dist is None or dist < best_dist:
            best_dist, best_pid = dist, pid
    if best_pid is not None and best_dist < FACE_MATCH_THRESHOLD:
        return best_pid, best_dist
    return None, None

def _next_person_name(people):
    n = 1
    existing = {p['name'] for p in people.values()}
    while f'Kişi {n}' in existing:
        n += 1
    return f'Kişi {n}'

def _load_image_for_faces(full_path):
    """HEIC dahil her formatı okuyup küçültülmüş RGB numpy array olarak döndürür.
    scale: küçültme oranı — bbox'ları orijinal boyuta geri çevirmek için saklanır."""
    from PIL import Image
    img = Image.open(full_path).convert('RGB')
    scale = 1.0
    if max(img.size) > FACE_SCAN_MAX_DIM:
        scale = FACE_SCAN_MAX_DIM / max(img.size)
        img = img.resize((max(1, int(img.size[0]*scale)), max(1, int(img.size[1]*scale))))
    return np.array(img), scale

def _recompute_person_centroid(db, pid):
    """Bir kişinin merkez vektörünü, ona atanmış tüm yüzlerin ortalaması olarak yeniden hesaplar.
    Hiç yüzü kalmadıysa kişiyi tamamen siler."""
    encs = [np.array(f['encoding']) for f in db['faces'].values() if f.get('person_id') == pid]
    if not encs:
        db['people'].pop(pid, None)
        return
    db['people'][pid]['centroid'] = np.mean(encs, axis=0).tolist()
    db['people'][pid]['count']    = len(encs)
    valid_ids = [fid for fid, f in db['faces'].items() if f.get('person_id') == pid]
    if db['people'][pid].get('cover_face_id') not in valid_ids:
        db['people'][pid]['cover_face_id'] = valid_ids[0] if valid_ids else None

def process_new_faces(limit=FACE_BATCH_SIZE):
    """Galerideki henüz taranmamış fotoğrafları yüz tanımadan geçirir.
    En yeni fotoğraflar önce işlenir, böylece az önce yüklenen fotoğraflar
    bekleyen eski fotoğraf yığınının arkasında kalmadan kısa sürede gruplanır."""
    try:
        import face_recognition
    except ImportError:
        return 0  # kütüphane kurulu değilse sessizce çık, servis çalışmaya devam etsin

    data  = scan_gallery()
    items = [it for it in data['items'] if it['type'] == 'image']

    with faces_lock:
        db = load_faces_db()

    processed_count = 0
    for it in items:
        if processed_count >= limit:
            break
        gid = it['id']
        rec = db['processed'].get(gid)
        if rec and rec.get('mtime') == it['mtime']:
            continue

        full = os.path.join(GALLERY_DIR, it['rel'])
        face_ids = []
        try:
            arr, scale = _load_image_for_faces(full)
            locations = face_recognition.face_locations(arr, model='hog')
            encodings = face_recognition.face_encodings(arr, known_face_locations=locations)

            with faces_lock:
                for loc, enc in zip(locations, encodings):
                    enc_list = enc.tolist()
                    pid, _ = _find_best_person(enc_list, db['people'])
                    if pid is None:
                        pid = str(uuid.uuid4())[:8]
                        db['people'][pid] = {
                            'name': _next_person_name(db['people']),
                            'centroid': enc_list, 'count': 1, 'cover_face_id': None,
                        }
                    else:
                        p = db['people'][pid]
                        c, n = np.array(p['centroid']), p['count']
                        p['centroid'] = (((c * n) + np.array(enc_list)) / (n + 1)).tolist()
                        p['count']    = n + 1

                    face_id = str(uuid.uuid4())[:12]
                    db['faces'][face_id] = {
                        'photo_id': gid, 'person_id': pid,
                        'bbox': list(loc), 'scale': scale,
                        'manual': False, 'encoding': enc_list,
                    }
                    if not db['people'][pid]['cover_face_id']:
                        db['people'][pid]['cover_face_id'] = face_id
                    face_ids.append(face_id)
        except Exception as e:
            print(f"Yüz tanıma hatası ({it['name']}): {e}")

        with faces_lock:
            db['processed'][gid] = {'mtime': it['mtime'], 'faces': face_ids}
        processed_count += 1

    if processed_count > 0:
        with faces_lock:
            save_faces_db(db)
        print(f"✓ Yüz taraması: {processed_count} fotoğraf işlendi")

    return processed_count


def _face_scan_thread():
    while True:
        try:
            process_new_faces()
        except Exception as e:
            print(f"Yüz tarama thread hatası: {e}")
        time.sleep(FACE_SCAN_INTERVAL)

threading.Thread(target=_face_scan_thread, daemon=True).start()


@app.get('/api/faces/status')
def faces_status():
    data = scan_gallery()
    total_images = len([it for it in data['items'] if it['type'] == 'image'])
    with faces_lock:
        db = load_faces_db()
    processed = len(db['processed'])
    return {
        'total_images': total_images,
        'processed': processed,
        'pending': max(0, total_images - processed),
        'people_count': len([p for p in db['people'].values() if p.get('count', 0) > 0]),
    }


@app.get('/api/faces/people')
def faces_people():
    with faces_lock:
        db = load_faces_db()
    people = []
    for pid, p in db['people'].items():
        if p.get('count', 0) <= 0: continue
        people.append({
            'id': pid, 'name': p['name'],
            'count': p['count'], 'cover_face_id': p.get('cover_face_id'),
        })
    people.sort(key=lambda x: x['count'], reverse=True)
    return {'people': people}


class RenamePersonReq(BaseModel):
    name: str

@app.post('/api/faces/people/{pid}/rename')
def faces_rename_person(pid: str, req: RenamePersonReq):
    name = req.name.strip()
    if not name: raise HTTPException(400, 'İsim boş olamaz')
    with faces_lock:
        db = load_faces_db()
        if pid not in db['people']: raise HTTPException(404, 'Kişi bulunamadı')
        db['people'][pid]['name'] = name
        save_faces_db(db)
    return {'ok': True}


@app.delete('/api/faces/people/{pid}')
def faces_delete_person(pid: str):
    """Kişiyi siler, yüzleri 'etiketsiz' bırakır (encoding korunur, tekrar gruplanabilir)."""
    with faces_lock:
        db = load_faces_db()
        if pid not in db['people']: raise HTTPException(404, 'Kişi bulunamadı')
        for f in db['faces'].values():
            if f.get('person_id') == pid:
                f['person_id'] = None
        db['people'].pop(pid, None)
        save_faces_db(db)
    return {'ok': True}


@app.get('/api/faces/people/{pid}/photos')
def faces_person_photos(pid: str, page: int = 1, limit: int = 30):
    with faces_lock:
        db = load_faces_db()
    if pid not in db['people']:
        raise HTTPException(404, 'Kişi bulunamadı')

    photo_ids, seen = [], set()
    for f in db['faces'].values():
        if f.get('person_id') == pid and f['photo_id'] not in seen:
            seen.add(f['photo_id']); photo_ids.append(f['photo_id'])

    gdata = scan_gallery()
    items = [gdata['index'][gid] for gid in photo_ids if gid in gdata['index']]
    items.sort(key=lambda x: x['mtime'], reverse=True)

    if page < 1: page = 1
    if limit < 1: limit = 1
    total = len(items)
    pages = max(1, (total + limit - 1) // limit)
    start = (page - 1) * limit
    out = []
    for it in items[start:start + limit]:
        dt = datetime.datetime.fromtimestamp(it['mtime'], TZ)
        out.append({
            'id': it['id'], 'type': it['type'], 'name': it['name'],
            'size': it['size'], 'date': dt.strftime('%d.%m.%Y %H:%M'),
        })
    return {'items': out, 'total': total, 'page': page, 'pages': pages}


@app.get('/api/faces/photo/{gid}')
def faces_in_photo(gid: str):
    """Belirli bir fotoğraftaki tüm yüzleri ve atandıkları kişiyi döndürür
    (galeri lightbox'ında düzeltme arayüzü için)."""
    with faces_lock:
        db = load_faces_db()
    result = []
    for fid, f in db['faces'].items():
        if f['photo_id'] == gid:
            person = db['people'].get(f.get('person_id'), {}) if f.get('person_id') else {}
            result.append({
                'face_id': fid,
                'person_id': f.get('person_id'),
                'person_name': person.get('name', 'Etiketsiz'),
            })
    return {'faces': result}


@app.get('/api/faces/thumb/{face_id}')
def faces_thumb(face_id: str):
    with faces_lock:
        db = load_faces_db()
    f = db['faces'].get(face_id)
    if not f: raise HTTPException(404, 'Yüz bulunamadı')

    item = scan_gallery()['index'].get(f['photo_id'])
    if not item: raise HTTPException(404, 'Fotoğraf bulunamadı')
    full = os.path.join(GALLERY_DIR, item['rel'])

    os.makedirs(FACE_THUMB_DIR, exist_ok=True)
    thumb_path = os.path.join(FACE_THUMB_DIR, face_id + '.jpg')
    if not os.path.exists(thumb_path):
        try:
            from PIL import Image
            img = Image.open(full).convert('RGB')
            scale = f.get('scale', 1.0)
            if scale != 1.0:
                img = img.resize((max(1, int(img.size[0]*scale)), max(1, int(img.size[1]*scale))))
            top, right, bottom, left = f['bbox']
            w, h = right - left, bottom - top
            pad_x, pad_y = int(w * 0.3), int(h * 0.3)
            box = (
                max(0, left - pad_x), max(0, top - pad_y),
                min(img.size[0], right + pad_x), min(img.size[1], bottom + pad_y),
            )
            crop = img.crop(box)
            crop.thumbnail((300, 300))
            crop.save(thumb_path, 'JPEG', quality=85)
        except Exception as e:
            raise HTTPException(500, f'Yüz önizleme oluşturulamadı: {e}')
    return FileResponse(thumb_path, media_type='image/jpeg')


class FaceReassignReq(BaseModel):
    face_ids: list[str]
    person_id: str = ''
    new_name: str = ''

@app.post('/api/faces/reassign')
def faces_reassign(req: FaceReassignReq):
    """Seçilen yüzleri mevcut bir kişiye ya da yeni oluşturulan bir kişiye taşır.
    Kaynak ve hedef kişilerin merkez vektörü yeniden hesaplanır."""
    if not req.face_ids:
        raise HTTPException(400, 'Yüz seçilmedi')
    with faces_lock:
        db = load_faces_db()

        target_pid = req.person_id.strip()
        if not target_pid:
            name = req.new_name.strip() or _next_person_name(db['people'])
            target_pid = str(uuid.uuid4())[:8]
            db['people'][target_pid] = {'name': name, 'centroid': None, 'count': 0, 'cover_face_id': None}
        elif target_pid not in db['people']:
            raise HTTPException(404, 'Hedef kişi bulunamadı')

        affected_pids = {target_pid}
        for fid in req.face_ids:
            f = db['faces'].get(fid)
            if not f: continue
            old_pid = f.get('person_id')
            if old_pid: affected_pids.add(old_pid)
            f['person_id'] = target_pid
            f['manual'] = True

        for pid in list(affected_pids):
            if pid in db['people']:
                _recompute_person_centroid(db, pid)

        save_faces_db(db)
    return {'ok': True, 'person_id': target_pid}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API — PUSH BİLDİRİMLERİ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get('/api/push/vapid-public')
def get_vapid_public():
    if not VAPID_PUBLIC_KEY_B64:
        raise HTTPException(500, 'VAPID anahtarı yapılandırılmadı')
    return {'key': VAPID_PUBLIC_KEY_B64}

class PushSubscription(BaseModel):
    endpoint: str
    keys: dict

@app.post('/api/push/subscribe')
def push_subscribe(sub: PushSubscription):
    subs = load_json(SUBSCRIPTIONS_FILE, [])
    for s in subs:
        if s.get('endpoint') == sub.endpoint:
            return {'ok': True, 'message': 'Zaten kayıtlı'}
    subs.append({'endpoint': sub.endpoint, 'keys': sub.keys})
    save_json(SUBSCRIPTIONS_FILE, subs)
    return {'ok': True}

@app.post('/api/push/unsubscribe')
def push_unsubscribe(sub: PushSubscription):
    subs = load_json(SUBSCRIPTIONS_FILE, [])
    new = [s for s in subs if s.get('endpoint') != sub.endpoint]
    save_json(SUBSCRIPTIONS_FILE, new)
    return {'ok': True}

def send_push_notification(sub, title, body):
    try:
        from pywebpush import webpush, WebPushException
        webpush(
            subscription_info=sub,
            data=json.dumps({'title': title, 'body': body}),
            vapid_private_key=VAPID_PRIVATE_KEY_FILE,
            vapid_claims={'sub': VAPID_EMAIL},
        )
        return True
    except Exception as e:
        print(f"Push hatası: {e}")
        return False

def check_reminders_and_notify():
    now = datetime.datetime.now(TZ)
    reminders = load_json(REMINDERS_FILE, [])
    subs      = load_json(SUBSCRIPTIONS_FILE, [])
    if not subs: return
    for r in reminders:
        should_fire = False
        try:
            if r['type'] == 'once':
                fire = datetime.datetime.fromisoformat(r['fire_at'])
                if fire.tzinfo is None: fire = TZ.localize(fire)
                diff = (now - fire).total_seconds()
                if 0 <= diff < 60: should_fire = True
            elif r['type'] == 'repeat':
                if r.get('repeat_type') == 'gün':
                    if now.hour == r.get('hour') and now.minute == r.get('minute'):
                        should_fire = True
                elif r.get('repeat_type') == 'hafta':
                    if (now.weekday() == r.get('weekday') and
                            now.hour == r.get('hour') and
                            now.minute == r.get('minute')):
                        should_fire = True
        except Exception as e:
            print(f"Reminder kontrol hatası: {e}")
        if should_fire:
            for sub in subs:
                send_push_notification(sub, '⏰ Hatırlatıcı', r['text'])

def _reminder_thread():
    while True:
        time.sleep(60 - datetime.datetime.now().second)
        try:
            check_reminders_and_notify()
        except Exception as e:
            print(f"Reminder thread hatası: {e}")

threading.Thread(target=_reminder_thread, daemon=True).start()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STATIC / SPA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STATIC_DIR = os.path.join(BASE_DIR, 'static')
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')

@app.get('/{full_path:path}')
def serve_spa(full_path: str):
    index = os.path.join(BASE_DIR, 'index.html')
    return FileResponse(index) if os.path.exists(index) else {'error': 'index.html bulunamadı'}