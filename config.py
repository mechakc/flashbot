# config.py
import os
from dotenv import load_dotenv

load_dotenv(".env")

# WhatsApp
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# LNbits
LNBITS_URL = os.getenv("LNBITS_URL", "https://demo.lnbits.com")
LNBITS_API_KEY = os.getenv("LNBITS_API_KEY", "")
LNBITS_WALLET_ID = os.getenv("LNBITS_WALLET_ID", "")

# Serveur
PORT = int(os.getenv("PORT", 5000))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
DATABASE_PATH = os.getenv("DATABASE_PATH", "tontinebot.db")
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
