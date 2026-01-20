"""Configuration settings for the bot."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Telegram Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

# Bot Mode Configuration
# Options: 'dev' (polling) or 'prod' (webhook)
BOT_MODE = os.getenv('BOT_MODE', 'dev').lower()

# Webhook Configuration (for prod mode)
WEBHOOK_HOST = os.getenv('WEBHOOK_HOST', 'https://bot.bimuz.uz')
WEBHOOK_PATH = os.getenv('WEBHOOK_PATH', '/webhook')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', None)  # Optional secret token
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', '8443'))

# Backend API Configuration
# Try internal Docker service name first, then external URL
# In Docker: use 'http://api:8000' (service name from docker-compose)
# External: use 'https://api.bimuz.uz'
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000').rstrip('/')

# Redis Configuration (optional)
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
