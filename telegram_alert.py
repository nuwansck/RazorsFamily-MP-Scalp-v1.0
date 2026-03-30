"""
Telegram Alert System — RF Scalp Bot v2.0

Retries up to 3 times on 5xx errors with exponential backoff.
HTTP 429 (rate-limit) respects the Retry-After header.
4xx errors (bad token, bad chat_id) are NOT retried — they are config errors.

v2.0: Added send_document() for /export command and start_command_listener()
polling thread that responds to /export by sending trade_history.json.
"""
import json
import logging
import os
import threading
import time
from pathlib import Path

import requests

from config_loader import load_secrets, load_settings

log = logging.getLogger(__name__)

_MAX_RETRIES  = 3
_RETRY_DELAYS = (2, 5)

# Data directory — matches state_utils.DATA_DIR
_DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))


class TelegramAlert:
    def __init__(self):
        secrets      = load_secrets()
        self.token   = secrets.get("TELEGRAM_TOKEN", "")
        self.chat_id = secrets.get("TELEGRAM_CHAT_ID", "")

    def send(self, message: str) -> bool:
        if not self.token or not self.chat_id:
            log.warning("Telegram not configured.")
            return False

        _bot_name = load_settings().get("bot_name", "RF Scalp")
        url  = f"https://api.telegram.org/bot{self.token}/sendMessage"
        text = f"\U0001f916 {_bot_name}\n{chr(0x2500) * 22}\n{message}"

        for attempt in range(_MAX_RETRIES):
            try:
                r = requests.post(
                    url,
                    data={"chat_id": self.chat_id, "text": text},
                    timeout=10,
                )
                if r.status_code == 200:
                    if attempt:
                        log.info("Telegram sent (attempt %d).", attempt + 1)
                    else:
                        log.info("Telegram sent!")
                    return True

                if r.status_code == 429:
                    retry_after = int(r.headers.get("Retry-After", 5))
                    log.warning(
                        "Telegram rate-limited (429) — waiting %ds (attempt %d/%d).",
                        retry_after, attempt + 1, _MAX_RETRIES,
                    )
                    time.sleep(retry_after)
                    continue

                if r.status_code < 500:
                    log.warning("Telegram %s (no retry): %s", r.status_code, r.text[:200])
                    return False

                log.warning("Telegram 5xx (attempt %d/%d): HTTP %s", attempt + 1, _MAX_RETRIES, r.status_code)
                if attempt < len(_RETRY_DELAYS):
                    time.sleep(_RETRY_DELAYS[attempt])

            except requests.RequestException as exc:
                log.warning("Telegram network error (attempt %d/%d): %s", attempt + 1, _MAX_RETRIES, exc)
                if attempt < len(_RETRY_DELAYS):
                    time.sleep(_RETRY_DELAYS[attempt])

        log.error("Telegram failed after %d attempts.", _MAX_RETRIES)
        return False

    def send_document(self, file_path: Path, caption: str = "") -> bool:
        """Send a file as a Telegram document attachment."""
        if not self.token or not self.chat_id:
            log.warning("Telegram not configured.")
            return False
        if not file_path.exists():
            log.warning("send_document: file not found: %s", file_path)
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendDocument"
        try:
            with open(file_path, "rb") as fh:
                r = requests.post(
                    url,
                    data={"chat_id": self.chat_id, "caption": caption},
                    files={"document": (file_path.name, fh, "application/json")},
                    timeout=30,
                )
            if r.status_code == 200:
                log.info("Telegram document sent: %s", file_path.name)
                return True
            log.warning("Telegram document failed: HTTP %s: %s", r.status_code, r.text[:200])
            return False
        except Exception as exc:
            log.warning("Telegram document error: %s", exc)
            return False


def _handle_export(alert: "TelegramAlert") -> None:
    """Read trade_history.json and send as file attachment."""
    history_file = _DATA_DIR / "trade_history.json"
    if not history_file.exists():
        alert.send("No trade history found on volume.")
        return
    try:
        trades = json.loads(history_file.read_text(encoding="utf-8"))
        filled = [t for t in trades if isinstance(t, dict) and t.get("status") == "FILLED"]
        caption = (
            f"trade_history.json\n"
            f"{len(trades)} total records  |  {len(filled)} filled trades"
        )
        ok = alert.send_document(history_file, caption=caption)
        if not ok:
            alert.send("Export failed — could not send file. Check logs.")
    except Exception as exc:
        log.warning("Export error: %s", exc)
        alert.send(f"Export error: {exc}")


def start_command_listener(alert: "TelegramAlert | None" = None) -> None:
    """
    Start a background polling thread that listens for Telegram commands.
    Supported commands:
      /export  — sends trade_history.json as a file attachment

    Security: only responds to messages from the configured TELEGRAM_CHAT_ID.
    Polls getUpdates every 30 seconds using long-polling offset.
    """
    if alert is None:
        alert = TelegramAlert()
    if not alert.token or not alert.chat_id:
        log.warning("Command listener: Telegram not configured — skipping.")
        return

    def _poll():
        offset   = None
        poll_url = f"https://api.telegram.org/bot{alert.token}/getUpdates"
        log.info("Telegram command listener started — polling for /export")

        while True:
            try:
                params = {"timeout": 25, "allowed_updates": ["message"]}
                if offset is not None:
                    params["offset"] = offset

                r = requests.get(poll_url, params=params, timeout=35)
                if r.status_code != 200:
                    log.warning("getUpdates HTTP %s", r.status_code)
                    time.sleep(30)
                    continue

                updates = r.json().get("result", [])
                for upd in updates:
                    offset = upd["update_id"] + 1
                    msg    = upd.get("message", {})
                    text   = msg.get("text", "").strip().lower()
                    chat   = str(msg.get("chat", {}).get("id", ""))

                    if chat != str(alert.chat_id):
                        continue

                    if text.startswith("/export"):
                        log.info("Received /export — sending trade_history.json")
                        _handle_export(alert)

            except Exception as exc:
                log.warning("Command listener error: %s", exc)

            time.sleep(30)

    t = threading.Thread(target=_poll, daemon=True, name="telegram-cmd-listener")
    t.start()
    log.info("Telegram /export command listener thread started.")
