"""
Structured JSON logging with rotating files.
Files: main.log, trades.log, alerts.log, regime.log
Each entry includes: timestamp, regime, probability, equity, positions, daily_pnl
"""

import json
import logging
import logging.handlers
import os
from datetime import datetime


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        doc = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("regime", "probability", "equity", "positions", "daily_pnl"):
            if hasattr(record, key):
                doc[key] = getattr(record, key)
        if record.exc_info:
            doc["exception"] = self.formatException(record.exc_info)
        return json.dumps(doc)


def _make_rotating_handler(path: str, max_bytes: int, backup_count: int) -> logging.Handler:
    handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    handler.setFormatter(StructuredFormatter())
    return handler


def setup_structured_logging(config: dict):
    monitoring_cfg = config.get("monitoring", {})
    log_dir = monitoring_cfg.get("log_dir", "logs")
    max_bytes = monitoring_cfg.get("log_max_bytes", 10 * 1024 * 1024)
    backup_count = monitoring_cfg.get("log_backup_count", 30)

    os.makedirs(log_dir, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(console)

    main_handler = _make_rotating_handler(os.path.join(log_dir, "main.log"), max_bytes, backup_count)
    main_handler.setLevel(logging.DEBUG)
    root.addHandler(main_handler)

    trade_logger = logging.getLogger("trades")
    trade_logger.addHandler(
        _make_rotating_handler(os.path.join(log_dir, "trades.log"), max_bytes, backup_count)
    )

    alert_logger = logging.getLogger("alerts")
    alert_logger.addHandler(
        _make_rotating_handler(os.path.join(log_dir, "alerts.log"), max_bytes, backup_count)
    )

    regime_logger = logging.getLogger("regime")
    regime_logger.addHandler(
        _make_rotating_handler(os.path.join(log_dir, "regime.log"), max_bytes, backup_count)
    )


def log_trade(symbol: str, direction: str, qty: float, price: float, regime: str, pnl: float = 0.0):
    logger = logging.getLogger("trades")
    logger.info(
        f"TRADE {direction} {qty} {symbol} @ ${price:.2f}",
        extra={"regime": regime, "pnl": pnl},
    )


def log_regime_change(old_regime: str, new_regime: str, probability: float, equity: float):
    logger = logging.getLogger("regime")
    logger.warning(
        f"REGIME CHANGE: {old_regime} → {new_regime} (p={probability:.2f})",
        extra={"regime": new_regime, "probability": probability, "equity": equity},
    )
