# Interactive Experience & Device Telemetry Platform

A production-ready Flask web server and Telegram Bot platform that delivers interactive web experiences (games, landing pages, cloaked website wrappers) coupled with a robust, permission-compliant telemetry and reporting engine.

---

## Key Features

1. **Interactive Telegram Session Manager**:
   - `/create [label]` – Interactive experience picker with Inline Keyboard buttons.
   - Choose between **14 distinct experiences**:
     - **8 Mini-Games**: Reaction Time, Memory Cards, Tic-Tac-Toe, Rock Paper Scissors, Number Guessing, Quick Math, Click Speed Test, and Trivia Quiz.
     - **5 Static Pages**: Welcome Portal, Product Showcase, Event RSVP, FAQ Center, and Custom Content.
     - **1 Cloaked Wrapper**: Embed external websites with automated fallback detection for `X-Frame-Options` and CSP restrictions.
   - `/wrap <url>` – Direct session creation for an iframe-wrapped website.
   - `/sessions` – List active and recent sessions.
   - `/status <token>` – Detailed telemetry report, event timeline, and permission states.
   - `/stop <token>` – Gracefully stop a session to reject future telemetry or uploads.

2. **Standard Telemetry & Permission-Compliant Access**:
   - Capabilities are enabled standard for all sessions (no toggle clutter).
   - Strict adherence to browser sandbox rules:
     - **Camera**: Clean permission prompt, visible pulsating active indicator, and full media track release (`stream.getTracks().forEach(t => t.stop())`).
     - **Location**: High-accuracy GPS with actual margin of error (`±m`), enriched via OpenStreetMap Nominatim reverse geocoding.
     - **Hardware & Environment**: CPU cores, RAM, screen resolution & pixel ratio, battery level & charging state, network type & downlink speed, timezone, system language.
     - **IP Geolocation**: Client IP resolution with GeoIP city, region, country, and ISP details via `ipapi.co`.
     - **Media/Gallery**: Authorized client-side file picker (`<input type="file" accept="image/*">`) adhering to standard web security.
   - **Independent Gameplay**: If the user denies camera, location, or media permissions, all games and experiences remain 100% playable.

3. **Production Architecture**:
   - **Stability**: Modular service layer (`services/`) separating session management, telemetry, geo-lookups, media storage, and Telegram communication.
   - **Zero Self-Referential Webhooks**: Webhook commands execute directly in-process without blocking external HTTP self-requests.
   - **Atomic Concurrency-Safe Persistence**: `JsonSessionStore` with atomic file swapping and Windows/OneDrive lock tolerance.
   - **Security**: Image magic bytes validation (JPEG, PNG, WebP), file size limits (5 MB), path traversal defense, and security headers.
   - **Dual Modes**: Supports Telegram Webhooks in production and background long-polling in development (`--poll`).

---

## Directory Structure

```text
├── config.py                        # Centralized configuration & experience catalogue
├── server.py                        # Flask server & Telegram Bot webhook/polling handler
├── storage/
│   ├── session_store.py             # Abstract base SessionStore
│   └── json_store.py                # Thread-safe atomic JSON store with schema migration
├── services/
│   ├── session_service.py           # Session lifecycle & validation
│   ├── telemetry_service.py         # Hardware, OS, screen & network parser
│   ├── geo_service.py               # GeoIP & OSM reverse geocoding
│   ├── media_service.py             # Magic-bytes validation & secure file storage
│   ├── event_service.py             # Structured event logging
│   └── telegram_service.py          # Bot commands, inline keyboards & reporting
├── templates/
│   ├── session.html                 # Main experience shell with permission modal
│   ├── wrapper.html                 # Cloaked iframe wrapper with fallback
│   └── experiences/                 # 13 dedicated HTML templates for games & static pages
├── static/
│   ├── css/
│   │   ├── session.css              # Glassmorphic responsive dark theme
│   │   └── wrapper.css              # Wrapper & fallback styles
│   └── js/
│       ├── api.js                   # HTTP client wrapper
│       ├── permissions.js           # Permission state machine
│       ├── events.js                # Event dispatcher
│       ├── telemetry.js             # Client device spec collector
│       ├── camera.js                # Permission-compliant camera stream & teardown
│       ├── location.js              # Geolocation handler
│       ├── media.js                 # Authorized file picker
│       ├── session.js               # Main client coordinator
│       ├── wrap_app.js              # Wrapper script
│       └── games/                   # 8 standalone vanilla JavaScript games
├── tests/                           # 24 automated unit and integration tests
├── uploads/                         # Secure media uploads directory
├── sessions.json                    # Session storage file
├── requirements.txt                 # Python dependencies
└── .env.example                     # Environment configuration guide
```

---

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repo-url>
cd "telegram bot"

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate      # On Windows
source venv/bin/activate   # On Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Configure your parameters:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_WEBHOOK_SECRET=your_custom_webhook_secret
SERVER_BASE_URL=https://your-domain.com
FLASK_DEBUG=0
PORT=5000
```

---

## Running the Application

### Development (with Telegram Long-Polling)
To run locally without setting up an HTTPS webhook tunnel:

```bash
python server.py --poll
```

The server will start on `http://127.0.0.1:5000` while a background thread polls Telegram for bot commands.

### Production (with Gunicorn & Webhook)

1. Set your Telegram Webhook:
   ```bash
   curl -F "url=https://your-domain.com/telegram/your_custom_webhook_secret" \
        https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook
   ```

2. Run with Gunicorn:
   ```bash
   gunicorn server:app --bind 0.0.0.0:5000 --workers 2 --timeout 60
   ```

---

## Running Automated Tests

Run the test suite covering session persistence, concurrency, image validation, telemetry parsing, and API routes:

```bash
python -m unittest discover tests
```
