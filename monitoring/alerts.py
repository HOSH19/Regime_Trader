"""
Alert system for critical trading events.
Rate-limited: 1 alert per event type per 15 minutes.
Delivery: console, log file, optional email, optional webhook.
"""

import logging
import os
import time
from typing import Optional

logger = logging.getLogger("alerts")

ALERT_EVENTS = [
    "regime_change",
    "circuit_breaker",
    "large_pnl",
    "data_feed_down",
    "api_lost",
    "hmm_retrained",
    "flicker_exceeded",
    "system_error",
]


class AlertManager:
    def __init__(self, config: dict):
        self.cfg = config
        self.rate_limit_secs = config.get("monitoring", {}).get("alert_rate_limit_minutes", 15) * 60
        self._last_sent: dict = {}
        self._email = os.getenv("ALERT_EMAIL") or config.get("alerts", {}).get("email", "")
        self._webhook = os.getenv("ALERT_WEBHOOK_URL") or config.get("alerts", {}).get("webhook_url", "")

    def send(self, event_type: str, message: str):
        now = time.time()
        last = self._last_sent.get(event_type, 0)
        if now - last < self.rate_limit_secs:
            return

        self._last_sent[event_type] = now
        logger.warning(f"[ALERT:{event_type.upper()}] {message}")

        if self._webhook:
            self._send_webhook(event_type, message)
        if self._email:
            self._send_email(event_type, message)

    def _send_webhook(self, event_type: str, message: str):
        try:
            import requests
            payload = {"event": event_type, "message": message, "timestamp": time.time()}
            resp = requests.post(self._webhook, json=payload, timeout=5)
            if resp.status_code != 200:
                logger.debug(f"Webhook returned {resp.status_code}")
        except Exception as e:
            logger.debug(f"Webhook failed: {e}")

    def _send_email(self, event_type: str, message: str):
        try:
            import smtplib
            from email.message import EmailMessage

            msg = EmailMessage()
            msg.set_content(f"Event: {event_type}\n\n{message}")
            msg["Subject"] = f"[RegimeTrader] {event_type.upper()}"
            msg["From"] = self._email
            msg["To"] = self._email

            with smtplib.SMTP("localhost") as smtp:
                smtp.send_message(msg)
        except Exception as e:
            logger.debug(f"Email alert failed: {e}")

    def on_regime_state(self, current_state, previous_state):
        if previous_state and current_state:
            if (hasattr(previous_state, "label") and hasattr(current_state, "label")
                    and previous_state.label != current_state.label
                    and current_state.is_confirmed):
                self.send(
                    "regime_change",
                    f"Regime changed: {previous_state.label} → {current_state.label} "
                    f"(p={current_state.probability:.2f})",
                )

        if current_state and hasattr(current_state, "probability"):
            if current_state.probability < self.cfg.get("hmm", {}).get("min_confidence", 0.55):
                pass

    def on_large_pnl(self, symbol: str, pnl_pct: float, threshold: float = 0.05):
        if abs(pnl_pct) >= threshold:
            direction = "gain" if pnl_pct > 0 else "loss"
            self.send("large_pnl", f"Large {direction}: {symbol} {pnl_pct*100:+.1f}%")

    def on_data_feed_down(self, symbol: str):
        self.send("data_feed_down", f"Data feed down for {symbol}")

    def on_api_error(self, error: str):
        self.send("api_lost", f"Alpaca API error: {error}")

    def on_flicker_exceeded(self, flicker_rate: int, threshold: int):
        self.send("flicker_exceeded", f"HMM flicker rate {flicker_rate} exceeds threshold {threshold}")
