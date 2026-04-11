"""
Alpaca API wrapper. Credentials from .env (NEVER hardcoded).
Paper trading by default. Live requires explicit typed confirmation.
"""

import logging
import os
import time
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

PAPER_BASE_URL = "https://paper-api.alpaca.markets"
LIVE_BASE_URL = "https://api.alpaca.markets"


class AlpacaClient:
    def __init__(self, config: dict):
        self.cfg = config
        self.paper_trading = config.get("broker", {}).get("paper_trading", True)
        self._client = None
        self._trading_client = None
        self._data_client = None
        self._connect()

    def _connect(self):
        from alpaca.trading.client import TradingClient
        from alpaca.data.historical import StockHistoricalDataClient

        api_key = os.getenv("ALPACA_API_KEY") or self.cfg.get("alpaca", {}).get("api_key")
        secret_key = os.getenv("ALPACA_SECRET_KEY") or self.cfg.get("alpaca", {}).get("secret_key")

        if not api_key or not secret_key:
            raise ValueError(
                "Alpaca credentials not found. Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env"
            )

        if not self.paper_trading:
            confirm = input(
                "\n⚠️  LIVE TRADING MODE. Type 'YES I UNDERSTAND THE RISKS' to confirm: "
            ).strip()
            if confirm != "YES I UNDERSTAND THE RISKS":
                raise SystemExit("Live trading confirmation failed. Exiting.")

        self._trading_client = TradingClient(
            api_key=api_key,
            secret_key=secret_key,
            paper=self.paper_trading,
        )
        self._data_client = StockHistoricalDataClient(
            api_key=api_key,
            secret_key=secret_key,
        )
        logger.info(f"Alpaca client connected ({'PAPER' if self.paper_trading else 'LIVE'})")

    def health_check(self) -> bool:
        try:
            account = self._trading_client.get_account()
            return account.status == "ACTIVE"
        except Exception as e:
            logger.error(f"Alpaca health check failed: {e}")
            return False

    def reconnect(self, max_retries: int = 5):
        for attempt in range(max_retries):
            try:
                self._connect()
                if self.health_check():
                    logger.info("Alpaca reconnected successfully")
                    return
            except Exception as e:
                wait = 2 ** attempt
                logger.warning(f"Reconnect attempt {attempt+1}/{max_retries} failed: {e}. Waiting {wait}s")
                time.sleep(wait)
        raise ConnectionError("Failed to reconnect to Alpaca after max retries")

    def get_account(self):
        return self._trading_client.get_account()

    def get_positions(self):
        return self._trading_client.get_all_positions()

    def get_order_history(self, limit: int = 50):
        from alpaca.trading.requests import GetOrdersRequest
        req = GetOrdersRequest(limit=limit)
        return self._trading_client.get_orders(filter=req)

    def is_market_open(self) -> bool:
        clock = self._trading_client.get_clock()
        return clock.is_open

    def get_clock(self):
        return self._trading_client.get_clock()

    def get_available_margin(self) -> float:
        account = self.get_account()
        return float(account.buying_power)

    @property
    def trading_client(self):
        return self._trading_client

    @property
    def data_client(self):
        return self._data_client
