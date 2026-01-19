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

# Backend API Configuration
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000').rstrip('/')

# Redis Configuration (optional)
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
