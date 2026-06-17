import os
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION (From Environment Variables) ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '')
LOCATION = os.getenv('LOCATION', 'Konya,tr')
DATA_FILE = 'wallet_data.json'
HISTORY_FILE = 'price_history.json'
USER_LOGIN = os.getenv('USER_LOGIN', '')
WOL_MAC_ADDRESS = os.getenv('WOL_MAC_ADDRESS', '')
METALPRICE_API_KEY = os.getenv('METALPRICE_API_KEY', '')
HUGGINGFACE_TOKEN = os.getenv('HUGGINGFACE_TOKEN', '')