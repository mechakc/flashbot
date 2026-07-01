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

# MoMo
MOMO_SUBSCRIPTION_KEY = os.getenv("MOMO_SUBSCRIPTION_KEY", "")
MOMO_API_USER = os.getenv("MOMO_API_USER", "")
MOMO_API_KEY = os.getenv("MOMO_API_KEY", "")
MOMO_ENVIRONMENT = os.getenv("MOMO_ENVIRONMENT", "sandbox")
MOMO_BASE_URL = os.getenv("MOMO_BASE_URL", "https://sandbox.momodeveloper.mtn.com")

# Flash
FLASH_API_KEY = os.getenv("FLASH_API_KEY", "")
FLASH_API_URL = os.getenv("FLASH_API_URL", "")

# Serveur
PORT = int(os.getenv("PORT", 5000))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
DATABASE_PATH = os.getenv("DATABASE_PATH", "tontinebot.db")
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
