# config.py
import os
from dotenv import load_dotenv

load_dotenv("flash.env")

# WhatsApp
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# MTN MoMo
MOMO_SUBSCRIPTION_KEY = os.getenv("MOMO_SUBSCRIPTION_KEY")
MOMO_API_USER = os.getenv("MOMO_API_USER")
MOMO_API_KEY = os.getenv("MOMO_API_KEY")
MOMO_ENVIRONMENT = os.getenv("MOMO_ENVIRONMENT", "sandbox")
MOMO_BASE_URL = "https://sandbox.momodeveloper.mtn.com"

# Flash
FLASH_API_KEY = os.getenv("FLASH_API_KEY", "")
FLASH_API_URL = os.getenv("FLASH_API_URL", "https://api.bitcoinflash.xyz")

# Serveur
PORT = int(os.getenv("PORT", 5000))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
DATABASE_PATH = os.getenv("DATABASE_PATH", "flashbot.db")