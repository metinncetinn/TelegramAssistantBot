import os
import requests
import json
import datetime
import pytz
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
import signal
import sys
import socket
import uuid
from botApi import *

load_dotenv()

ALTINKAYNAK_GOLD_URL     = 'https://static.altinkaynak.com/public/Gold'
ALTINKAYNAK_CURRENCY_URL = 'https://static.altinkaynak.com/public/Currency'

CURRENCY_ALIASES = {
    'usd':    ['usd', 'dolar', 'dollar', 'dlr', '$'],
    'eur':    ['eur', 'euro', 'avro', '€'],
    'gbp':    ['gbp', 'sterlin', 'pound', '£'],
    'jpy':    ['jpy', 'yen', 'japon'],
    'gram':   ['gram', 'gr', 'g'],
    'ceyrek': ['ceyrek', 'çeyrek'],
    'yarim':  ['yarim', 'yarım'],
    'tam':    ['tam', 't', 'teklik']
}

CURRENCY_NAMES = {
    'usd': 'Dolar', 'eur': 'Euro', 'gbp': 'Sterlin', 'jpy': 'Japon Yeni',
    'gram': 'Gram Altın', 'ceyrek': 'Çeyrek Altın',
    'yarim': 'Yarım Altın', 'tam': 'Tam Altın'
}

CURRENCY_SYMBOLS = {
    'usd': '$', 'eur': '€', 'gbp': '£', 'jpy': '¥',
    'gram': 'gr', 'ceyrek': '¼', 'yarim': '½', 'tam': '1'
}

REMINDERS_FILE = 'reminders.json'
app = None


def get_current_datetime_utc():
    return datetime.datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S')

def load_wallet():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
            for key in ['usd', 'eur', 'gbp', 'jpy', 'gram', 'ceyrek', 'yarim', 'tam']:
                if key not in data:
                    data[key] = {'amount': 0, 'cost': 0.0}
                elif isinstance(data[key], (int, float)):
                    data[key] = {'amount': data[key], 'cost': 0.0}
            return data
    except:
        pass
    return {k: {'amount': 0, 'cost': 0.0}
            for k in ['usd', 'eur', 'gbp', 'jpy', 'gram', 'ceyrek', 'yarim', 'tam']}

def save_wallet(wallet_data):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(wallet_data, f)
    except Exception as e:
        print(f"Wallet kaydetme hatası: {e}")

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return []

def save_history(history_data):
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history_data, f)
    except Exception as e:
        print(f"History kaydetme hatası: {e}")

def parse_turkish_number(value_str):
    try:
        value_str = value_str.replace('.', '').replace(',', '.')
        return float(value_str)
    except:
        return 0.0

def send_magic_packet(mac_address):
    try:
        mac = mac_address.replace(':', '').replace('-', '').replace('.', '')
        if len(mac) != 12:
            return False, "Geçersiz MAC adresi formatı"
        mac_bytes   = bytes.fromhex(mac)
        magic_packet = b'\xff' * 6 + mac_bytes * 16
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic_packet, ('255.255.255.255', 9))
        sock.close()
        return True, "Magic packet başarıyla gönderildi"
    except Exception as e:
        return False, f"Magic packet gönderme hatası: {str(e)}"


def get_current_rates():
    """Altinkaynak API'den tüm finansal verileri alır"""
    try:
        rates = {}

        print("📊 Para birimleri çekiliyor...")
        currency_resp = requests.get(ALTINKAYNAK_CURRENCY_URL, timeout=10)
        if currency_resp.status_code == 200:
            for item in currency_resp.json():
                kod   = item.get('Kod', '').upper()
                satis = item.get('Alis', '0')
                if   kod == 'USD': rates['usd'] = parse_turkish_number(satis)
                elif kod == 'EUR': rates['eur'] = parse_turkish_number(satis)
                elif kod == 'GBP': rates['gbp'] = parse_turkish_number(satis)
                elif kod == 'JPY': rates['jpy'] = parse_turkish_number(satis)
            print(f"✅ Para birimleri alındı: {list(rates.keys())}")
        else:
            print(f"❌ Para birimi API hatası: {currency_resp.status_code}")

        print("📊 Altın fiyatları çekiliyor...")
        gold_resp = requests.get(ALTINKAYNAK_GOLD_URL, timeout=10)
        if gold_resp.status_code == 200:
            for item in gold_resp.json():
                kod   = item.get('Kod', '').upper()
                satis = item.get('Satis', '0')
                # ── YENİ KODLAR ──────────────────────────
                if   kod == 'PGA': rates['gram']   = parse_turkish_number(satis)
                elif kod == 'PC':  rates['ceyrek'] = parse_turkish_number(satis)
                elif kod == 'PY':  rates['yarim']  = parse_turkish_number(satis)
                elif kod == 'PT':  rates['tam']    = parse_turkish_number(satis)
            print(f"✅ Altın fiyatları alındı: gram={rates.get('gram', 0):.2f}")
        else:
            print(f"❌ Altın API hatası: {gold_resp.status_code}")

        if len(rates) >= 6:
            print(f"✅ Toplam {len(rates)} veri alındı")
            return rates
        else:
            print(f"❌ Eksik veri: Sadece {len(rates)} veri alındı")
            return None

    except Exception as e:
        print(f"API genel hatası: {str(e)}")
        return None


def get_weather():
    try:
        url  = f'https://api.openweathermap.org/data/2.5/weather?q={LOCATION}&appid={OPENWEATHER_API_KEY}&units=metric&lang=tr'
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return "Hava durumu alınamadı"
        data = resp.json()
        temp = data['main']['temp']
        desc = data['weather'][0]['description']
        return f"🌤 {LOCATION}: {temp:.1f}°C, {desc.capitalize()}"
    except:
        return "Hava durumu alınamadı"


def generate_image(prompt, size="1024x1024"):
    """Hugging Face Inference API ile resim oluşturur"""
    try:
        if not HUGGINGFACE_TOKEN or HUGGINGFACE_TOKEN == '?':
            return False, "HUGGINGFACE_TOKEN ayarlanmamış!"

        width, height = 1024, 1024
        if size and 'x' in size:
            parts = size.split('x')
            try:
                width  = int(parts[0])
                height = int(parts[1])
            except ValueError:
                pass

        api_url = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
        headers = {"Authorization": f"Bearer {HUGGINGFACE_TOKEN}"}
        payload = {
            "inputs": prompt,
            "parameters": {"width": width, "height": height}
        }

        print(f"🎨 Resim oluşturuluyor ({width}x{height}): {prompt}")
        response = requests.post(api_url, headers=headers, json=payload, timeout=120)

        if response.status_code == 401:
            return False, "Geçersiz Hugging Face token!"
        if response.status_code == 503:
            try:
                error_data = response.json()
                if 'estimated_time' in error_data:
                    wait_time = int(error_data['estimated_time'])
                    return False, f"Model yükleniyor, {wait_time} saniye bekleyip tekrar deneyin."
            except:
                return False, "Model yükleniyor, 20-30 saniye sonra tekrar deneyin."

        response.raise_for_status()
        if not response.content or len(response.content) < 100:
            return False, "API boş yanıt döndü"

        print("✅ Resim başarıyla oluşturuldu!")
        return True, response.content

    except Exception as e:
        return False, f"Hata: {str(e)}"


def load_reminders():
    try:
        if os.path.exists(REMINDERS_FILE):
            with open(REMINDERS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return []

def save_reminders(reminders):
    try:
        with open(REMINDERS_FILE, 'w') as f:
            json.dump(reminders, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Hatırlatıcı kaydetme hatası: {e}")

def check_reminders_sync():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(check_reminders(), loop)
    except Exception as e:
        print(f"❌ check_reminders_sync hatası: {e}")


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) != 2:
            await update.message.reply_text(
                "💰 Kullanım: /add <birim> <miktar>\n\n"
                "Para Birimleri:\n• dolar, euro, sterlin, yen\n\n"
                "Altın:\n• gram, çeyrek, yarım, tam\n\n"
                "Örnek: /add dolar 100"
            )
            return

        currency_input = context.args[0].lower()
        amount         = float(context.args[1])
        currency       = None

        for main_currency, aliases in CURRENCY_ALIASES.items():
            if currency_input in aliases:
                currency = main_currency
                break

        if not currency:
            await update.message.reply_text("❌ Geçersiz birim!\n\nPara: dolar, euro, sterlin, yen\nAltın: gram, çeyrek, yarım, tam")
            return

        rates = get_current_rates()
        if not rates:
            await update.message.reply_text("❌ Anlık kur alınamadı, işlem yapılamadı!")
            return

        buy_rate = rates[currency]
        cost     = amount * buy_rate
        wallet   = load_wallet()
        wallet[currency]['amount'] += amount
        wallet[currency]['cost']   += cost
        save_wallet(wallet)

        total_amount = wallet[currency]['amount']
        total_cost   = wallet[currency]['cost']
        avg_rate     = total_cost / total_amount if total_amount > 0 else 0

        await update.message.reply_text(
            f"✅ {amount:,.2f} {CURRENCY_NAMES[currency]} eklendi\n"
            f"💵 Alış fiyatı: {buy_rate:,.2f} TL\n"
            f"💰 Ödenen: {cost:,.2f} TL\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Toplam: {total_amount:,.2f} {CURRENCY_SYMBOLS[currency]}\n"
            f"📈 Ort. maliyet: {avg_rate:,.2f} TL"
        )
    except ValueError:
        await update.message.reply_text("❌ Geçersiz miktar! Sayı girmelisiniz.")
    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {str(e)}")


async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) != 2:
            await update.message.reply_text("💸 Kullanım: /remove <birim> <miktar>\n\nÖrnek: /remove euro 50")
            return

        currency_input = context.args[0].lower()
        amount         = float(context.args[1])
        currency       = None

        for main_currency, aliases in CURRENCY_ALIASES.items():
            if currency_input in aliases:
                currency = main_currency
                break

        if not currency:
            await update.message.reply_text("❌ Geçersiz birim!")
            return

        wallet         = load_wallet()
        current_amount = wallet[currency]['amount']

        if current_amount < amount:
            await update.message.reply_text(f"❌ Yetersiz bakiye!\n📊 Mevcut {CURRENCY_NAMES[currency]}: {current_amount:,.2f}")
            return

        ratio        = amount / current_amount
        removed_cost = wallet[currency]['cost'] * ratio
        wallet[currency]['amount'] -= amount
        wallet[currency]['cost']   -= removed_cost
        save_wallet(wallet)

        await update.message.reply_text(
            f"✅ {amount:,.2f} {CURRENCY_NAMES[currency]} çıkarıldı\n"
            f"📊 Kalan: {wallet[currency]['amount']:,.2f} {CURRENCY_SYMBOLS[currency]}"
        )
    except ValueError:
        await update.message.reply_text("❌ Geçersiz miktar! Sayı girmelisiniz.")
    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {str(e)}")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        wallet = load_wallet()
        rates  = get_current_rates()
        if not rates:
            await update.message.reply_text("❌ Kur bilgisi alınamadı!")
            return

        message     = "💰 Portföy Durumu\n━━━━━━━━━━━━━━━━━━━━\n\n"
        total_value = total_cost = 0.0
        has_currency = has_gold = False

        def format_entry(currency, label):
            nonlocal total_value, total_cost
            entry  = wallet.get(currency, {'amount': 0, 'cost': 0.0})
            amount = entry['amount']
            cost   = entry['cost']
            if amount <= 0: return ""
            rate       = rates.get(currency, 0)
            curr_value = amount * rate
            pnl        = curr_value - cost
            pnl_pct    = (pnl / cost * 100) if cost > 0 else 0
            avg_rate   = cost / amount if amount > 0 else 0
            pnl_icon   = "📈" if pnl >= 0 else "📉"
            total_value += curr_value
            total_cost  += cost
            return (
                f"  {label}: {amount:,.2f} {CURRENCY_SYMBOLS[currency]}\n"
                f"  ├─ Anlık fiyat : {rate:,.2f} TL\n"
                f"  ├─ Ort. maliyet: {avg_rate:,.2f} TL\n"
                f"  ├─ Güncel değer: {curr_value:,.2f} TL\n"
                f"  └─ {pnl_icon} Kâr/Zarar : {pnl:+,.2f} TL ({pnl_pct:+.2f}%)\n\n"
            )

        for curr in ['usd', 'eur', 'gbp', 'jpy']:
            entry = format_entry(curr, CURRENCY_NAMES[curr])
            if entry:
                if not has_currency:
                    message += "💵 Para Birimleri:\n"
                    has_currency = True
                message += entry

        for gold in ['gram', 'ceyrek', 'yarim', 'tam']:
            entry = format_entry(gold, CURRENCY_NAMES[gold])
            if entry:
                if not has_gold:
                    message += "🏆 Altın:\n"
                    has_gold = True
                message += entry

        if not has_currency and not has_gold:
            message += "📭 Portföyünüz boş!"
        else:
            total_pnl     = total_value - total_cost
            total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
            pnl_icon      = "📈" if total_pnl >= 0 else "📉"
            message += (
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💼 Toplam maliyet: {total_cost:,.2f} TL\n"
                f"📊 Güncel değer  : {total_value:,.2f} TL\n"
                f"{pnl_icon} Net kâr/zarar  : {total_pnl:+,.2f} TL ({total_pnl_pct:+.2f}%)"
            )

        await update.message.reply_text(message)
    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {str(e)}")


async def day_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        history = load_history()
        if not history:
            await update.message.reply_text("❌ Geçmiş veri bulunamadı!")
            return

        yesterday      = datetime.datetime.now() - datetime.timedelta(days=1)
        yesterday_data = None
        for item in history:
            item_date = datetime.datetime.fromisoformat(item['date'])
            if item_date.date() == yesterday.date():
                yesterday_data = item
                break

        if not yesterday_data:
            await update.message.reply_text("❌ Dünün verisi bulunamadı!")
            return

        today_rates = get_current_rates()
        if not today_rates:
            await update.message.reply_text("❌ Güncel kurlar alınamadı!")
            return

        wallet  = load_wallet()
        message = "📈 24 Saatlik Değişim\n━━━━━━━━━━━━━━━━━━━━\n\n"
        total_change = 0
        has_data     = False

        for currency in ['usd', 'eur', 'gbp', 'jpy', 'gram', 'ceyrek', 'yarim', 'tam']:
            amount = wallet.get(currency, {}).get('amount', 0)
            if amount > 0:
                has_data  = True
                old_rate  = yesterday_data['rates'].get(currency, 0)
                new_rate  = today_rates.get(currency, 0)
                old_value = amount * old_rate
                new_value = amount * new_rate
                change    = new_value - old_value
                total_change += change
                change_percent = ((new_rate - old_rate) / old_rate * 100) if old_rate > 0 else 0
                change_icon    = "📈" if change > 0 else "📉" if change < 0 else "📊"
                message += (
                    f"{change_icon} {CURRENCY_NAMES[currency]}: {amount:,.2f}\n"
                    f"  Dün: {old_rate:,.2f} TL  →  Bugün: {new_rate:,.2f} TL\n"
                    f"  Değişim: {change:+,.2f} TL ({change_percent:+.2f}%)\n\n"
                )

        if not has_data:
            message += "📭 Portföyünüzde varlık yok!"
        else:
            change_icon = "📈" if total_change > 0 else "📉" if total_change < 0 else "📊"
            message += f"━━━━━━━━━━━━━━━━━━━━\n{change_icon} TOPLAM DEĞİŞİM: {total_change:+,.2f} TL"

        await update.message.reply_text(message)
    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {str(e)}")


async def hatırlat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text(
                "⏰ Hatırlatıcı Kullanımı:\n\n"
                "Tek seferlik:\n"
                "  /hatırlat 14:30 Doktora git\n"
                "  /hatırlat 2saat İlaç iç\n"
                "  /hatırlat 45dk Toplantı\n\n"
                "Tekrarlayan:\n"
                "  /hatırlat her gün 08:00 Vitamin al\n"
                "  /hatırlat her hafta pazartesi 09:00 Rapor\n\n"
                "Yönetim:\n"
                "  /hatırlat liste\n"
                "  /hatırlat sil <id>"
            )
            return

        args = context.args
        now  = datetime.datetime.now(pytz.timezone('Europe/Istanbul'))

        if args[0].lower() == 'liste':
            reminders = load_reminders()
            if not reminders:
                await update.message.reply_text("📭 Aktif hatırlatıcı yok.")
                return
            message = "⏰ Aktif Hatırlatıcılar:\n━━━━━━━━━━━━━━━━━━━━\n\n"
            for r in reminders:
                rid = r['id'][:6]
                if r['type'] == 'once':
                    fire_dt  = datetime.datetime.fromisoformat(r['fire_at'])
                    fire_str = fire_dt.strftime('%d.%m.%Y %H:%M')
                    message += f"🔔 [{rid}] {fire_str}\n    📝 {r['text']}\n\n"
                else:
                    message += f"🔄 [{rid}] {r['repeat_label']}\n    📝 {r['text']}\n\n"
            await update.message.reply_text(message)
            return

        if args[0].lower() == 'sil':
            if len(args) < 2:
                await update.message.reply_text("❌ Kullanım: /hatırlat sil <id>")
                return
            short_id  = args[1].lower()
            reminders = load_reminders()
            new_list  = [r for r in reminders if not r['id'].startswith(short_id)]
            if len(new_list) == len(reminders):
                await update.message.reply_text(f"❌ '{short_id}' ID'li hatırlatıcı bulunamadı.")
                return
            save_reminders(new_list)
            await update.message.reply_text("✅ Hatırlatıcı silindi.")
            return

        if args[0].lower() == 'her':
            if len(args) < 3:
                await update.message.reply_text("❌ Eksik parametre.")
                return
            repeat_type = args[1].lower()
            DAYS_TR = {
                'pazartesi': 0, 'salı': 1, 'çarşamba': 2,
                'perşembe': 3, 'cuma': 4, 'cumartesi': 5, 'pazar': 6
            }
            if repeat_type == 'gün':
                if len(args) < 4:
                    await update.message.reply_text("❌ Eksik: /hatırlat her gün 08:00 Mesaj")
                    return
                time_str      = args[2]
                reminder_text = ' '.join(args[3:])
                repeat_label  = f"Her gün {time_str}"
                weekday       = None
            elif repeat_type == 'hafta':
                if len(args) < 5:
                    await update.message.reply_text("❌ Eksik: /hatırlat her hafta pazartesi 09:00 Mesaj")
                    return
                day_str = args[2].lower()
                time_str      = args[3]
                reminder_text = ' '.join(args[4:])
                if day_str not in DAYS_TR:
                    await update.message.reply_text(f"❌ Geçersiz gün: {day_str}")
                    return
                weekday      = DAYS_TR[day_str]
                repeat_label = f"Her hafta {day_str.capitalize()} {time_str}"
            else:
                await update.message.reply_text("❌ 'her gün' veya 'her hafta' kullanın.")
                return

            try:
                hour, minute = map(int, time_str.split(':'))
            except:
                await update.message.reply_text("❌ Geçersiz saat formatı! Örnek: 08:00")
                return

            reminder = {
                'id': str(uuid.uuid4()), 'type': 'repeat',
                'repeat_type': repeat_type, 'weekday': weekday,
                'hour': hour, 'minute': minute,
                'text': reminder_text, 'repeat_label': repeat_label,
                'chat_id': update.message.chat_id
            }
            reminders = load_reminders()
            reminders.append(reminder)
            save_reminders(reminders)
            await update.message.reply_text(
                f"✅ Tekrarlayan hatırlatıcı kuruldu!\n\n"
                f"🔄 {repeat_label}\n📝 {reminder_text}\n🆔 {reminder['id'][:6]}"
            )
            return

        time_arg      = args[0].lower()
        reminder_text = ' '.join(args[1:])
        if not reminder_text:
            await update.message.reply_text("❌ Hatırlatıcı metni boş olamaz!")
            return

        fire_at = None
        for suffix in ['saat', 's']:
            if time_arg.endswith(suffix):
                try:
                    fire_at = now + datetime.timedelta(hours=float(time_arg.replace(suffix, '')))
                    break
                except: pass

        if not fire_at:
            for suffix in ['dakika', 'dk', 'min', 'm']:
                if time_arg.endswith(suffix):
                    try:
                        fire_at = now + datetime.timedelta(minutes=float(time_arg.replace(suffix, '')))
                        break
                    except: pass

        if not fire_at:
            try:
                hour, minute = map(int, time_arg.split(':'))
                fire_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if fire_at <= now:
                    fire_at += datetime.timedelta(days=1)
            except: pass

        if not fire_at:
            await update.message.reply_text("❌ Geçersiz zaman formatı!\n\nÖrnekler:\n  /hatırlat 14:30 Toplantı\n  /hatırlat 2saat İlaç iç\n  /hatırlat 45dk Fırın")
            return

        reminder = {
            'id': str(uuid.uuid4()), 'type': 'once',
            'fire_at': fire_at.isoformat(), 'text': reminder_text,
            'chat_id': update.message.chat_id
        }
        reminders = load_reminders()
        reminders.append(reminder)
        save_reminders(reminders)
        fire_str = fire_at.strftime('%d.%m.%Y %H:%M')
        await update.message.reply_text(
            f"✅ Hatırlatıcı kuruldu!\n\n🕐 Zaman: {fire_str}\n📝 Not: {reminder_text}\n🆔 {reminder['id'][:6]}"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {str(e)}")


async def check_reminders():
    if not app:
        return
    try:
        now       = datetime.datetime.now(pytz.timezone('Europe/Istanbul'))
        reminders = load_reminders()
        remaining = []
        fired_any = False

        for r in reminders:
            should_fire = False
            if r['type'] == 'once':
                fire_at = datetime.datetime.fromisoformat(r['fire_at'])
                if fire_at.tzinfo is None:
                    fire_at = pytz.timezone('Europe/Istanbul').localize(fire_at)
                if now >= fire_at:
                    should_fire = True
            elif r['type'] == 'repeat':
                if now.hour == r['hour'] and now.minute == r['minute']:
                    if r['repeat_type'] == 'gün':
                        should_fire = True
                    elif r['repeat_type'] == 'hafta' and now.weekday() == r.get('weekday'):
                        should_fire = True

            if should_fire:
                fired_any = True
                try:
                    await app.bot.send_message(chat_id=r['chat_id'], text=f"⏰ Hatırlatıcı!\n\n📝 {r['text']}")
                    print(f"✅ Hatırlatıcı gönderildi: {r['text']}")
                except Exception as e:
                    print(f"❌ Hatırlatıcı gönderilemedi: {e}")
                if r['type'] == 'repeat':
                    remaining.append(r)
            else:
                remaining.append(r)

        if fired_any:
            save_reminders(remaining)
    except Exception as e:
        print(f"❌ check_reminders hatası: {e}")


async def pc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        success, msg = send_magic_packet(WOL_MAC_ADDRESS)
        if success:
            await update.message.reply_text(f"💻 Magic packet gönderildi!\nMAC: {WOL_MAC_ADDRESS}\nBilgisayarınız yakında açılacak...")
        else:
            await update.message.reply_text(f"❌ Hata: {msg}")
    except Exception as e:
        await update.message.reply_text(f"❌ PC uyandırma hatası: {str(e)}")


async def olustur_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text("🎨 Kullanım: /olustur <prompt>\n\nÖrnek:\n/olustur sunset over mountains, digital art")
            return
        prompt      = ' '.join(context.args)
        waiting_msg = await update.message.reply_text(f"🎨 Resim oluşturuluyor...\nPrompt: {prompt}\n\n⏳ Lütfen bekleyin...")
        success, result = generate_image(prompt)
        if success:
            await update.message.reply_photo(photo=result, caption=f"✨ Prompt: {prompt}")
            await waiting_msg.delete()
        else:
            await waiting_msg.edit_text(f"❌ Resim oluşturulamadı!\nHata: {result}")
    except Exception as e:
        await update.message.reply_text(f"❌ Beklenmeyen hata: {str(e)}")


async def sistem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        import psutil
        cpu  = psutil.cpu_percent(interval=1)
        ram  = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = int(f.read()) / 1000.0
        except:
            temp = 0
        await update.message.reply_text(
            f"🖥 Raspberry Pi 5 Durumu:\n\n"
            f"CPU: {cpu}%\n"
            f"RAM: {ram.percent}% ({ram.used // (1024**3)}GB / {ram.total // (1024**3)}GB)\n"
            f"Disk: {disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)\n"
            f"Sıcaklık: {temp:.1f}°C"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Sistem bilgisi alınamadı: {e}")


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(get_weather())
    except Exception as e:
        await update.message.reply_text(f"❌ Hava durumu bilgisi alınamadı: {e}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Finansal Bot Komutları\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💰 Para İşlemleri:\n"
        "/add <birim> <miktar> - Ekle\n"
        "/remove <birim> <miktar> - Çıkar\n"
        "/durum - Portföy durumu\n"
        "/gun - Günlük değişim\n"
        "/test - API testi\n\n"
        "📊 Desteklenen Birimler:\n"
        "Para: dolar, euro, sterlin, yen\n"
        "Altın: gram, çeyrek, yarım, tam\n\n"
        "⏰ Hatırlatıcı:\n"
        "/hatırlat 14:30 Doktora git\n"
        "/hatırlat 2saat İlaç iç\n"
        "/hatırlat 45dk Fırın\n"
        "/hatırlat her gün 08:00 Vitamin\n"
        "/hatırlat her hafta pazartesi 09:00 Rapor\n"
        "/hatırlat liste\n"
        "/hatırlat sil <id>\n\n"
        "🎨 Resim:\n"
        "/olustur <prompt>\n\n"
        "💻 Sistem:\n"
        "/pc - PC uyandır\n"
        "/sistem - Pi durumu\n"
        "/hava - Hava durumu"
    )


async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rates = get_current_rates()
    if rates:
        message = "✅ Altinkaynak API Test\n━━━━━━━━━━━━━━━━━━━━\n\n💵 Para Birimleri:\n"
        for curr in ['usd', 'eur', 'gbp', 'jpy']:
            if curr in rates:
                message += f"{CURRENCY_NAMES[curr]}: {rates[curr]:,.2f} TL\n"
        message += "\n🏆 Altın Fiyatları:\n"
        for gold in ['gram', 'ceyrek', 'yarim', 'tam']:
            if gold in rates:
                message += f"{CURRENCY_NAMES[gold]}: {rates[gold]:,.2f} TL\n"
    else:
        message = "❌ API'den veri alınamadı!"
    await update.message.reply_text(message)


def save_daily_rates():
    try:
        rates = get_current_rates()
        if not rates: return
        history = load_history()
        today   = datetime.datetime.now().isoformat()
        found   = False
        for item in history:
            if item['date'][:10] == today[:10]:
                item['rates'] = rates
                found = True
                break
        if not found:
            history.append({'date': today, 'rates': rates})
        cutoff  = datetime.datetime.now() - datetime.timedelta(days=30)
        history = [item for item in history
                   if datetime.datetime.fromisoformat(item['date']) > cutoff]
        save_history(history)
        print(f"✅ Günlük kur kaydedildi: {len(rates)} veri")
    except Exception as e:
        print(f"❌ Günlük kur kaydetme hatası: {e}")


async def send_morning_report():
    try:
        if not app: return
        weather = get_weather()
        wallet  = load_wallet()
        rates   = get_current_rates()
        if not rates: return

        message   = f"🌅 Günaydın!\n\n{weather}\n\n💰 Portföy Özeti\n━━━━━━━━━━━━━━━━━━━━\n\n"
        total_try = 0
        has_data  = False

        for currency in ['usd', 'eur', 'gbp', 'jpy', 'gram', 'ceyrek', 'yarim', 'tam']:
            amount = wallet.get(currency, {}).get('amount', 0)
            if amount > 0:
                has_data  = True
                rate      = rates.get(currency, 0)
                try_value = amount * rate
                total_try += try_value
                message   += f"{CURRENCY_NAMES[currency]}: {amount:,.2f} = {try_value:,.2f} TL\n"

        message += f"\n📊 Toplam: {total_try:,.2f} TL" if has_data else "Portföyünüz boş!"
        await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        print(f"❌ Sabah raporu hatası: {e}")


def morning_report_sync():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(send_morning_report())
        loop.close()
    except Exception as e:
        print(f"❌ Morning report sync hatası: {e}")


def signal_handler(sig, frame):
    print('🛑 Bot kapatılıyor...')
    if 'scheduler' in globals():
        scheduler.shutdown()
    sys.exit(0)


def main():
    global app, scheduler
    print("🚀 Finansal Bot başlatılıyor...")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("add",      add_command))
    app.add_handler(CommandHandler("remove",   remove_command))
    app.add_handler(CommandHandler("durum",    status_command))
    app.add_handler(CommandHandler("gun",      day_command))
    app.add_handler(CommandHandler("pc",       pc_command))
    app.add_handler(CommandHandler("olustur",  olustur_command))
    app.add_handler(CommandHandler("sistem",   sistem_command))
    app.add_handler(CommandHandler("hava",     weather_command))
    app.add_handler(CommandHandler("help",     help_command))
    app.add_handler(CommandHandler("test",     test_command))
    app.add_handler(CommandHandler("hatırlat", hatırlat_command))

    scheduler = BackgroundScheduler(timezone='Europe/Istanbul')
    scheduler.add_job(save_daily_rates,     'cron',     hour=20,   minute=0)
    scheduler.add_job(morning_report_sync,  'cron',     hour=6,    minute=30)
    scheduler.add_job(check_reminders_sync, 'interval', minutes=1)

    signal.signal(signal.SIGINT,  signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        scheduler.start()
        print("⏰ Zamanlayıcı başlatıldı")
        print("🔍 Altinkaynak API test ediliyor...")
        test_rates = get_current_rates()
        if test_rates:
            print(f"✅ API başarılı - {len(test_rates)} veri alındı")
            for key, value in test_rates.items():
                print(f"  {key}: {value:.2f} TL")
        else:
            print("❌ API test başarısız")
        print("🚀 Bot çalışıyor...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(f"❌ Bot başlatma hatası: {e}")
        if 'scheduler' in globals():
            scheduler.shutdown()


if __name__ == '__main__':
    main()