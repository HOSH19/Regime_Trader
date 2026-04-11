"""
Real-time and historical market data via Alpaca.
WebSocket push for bar data — no polling.
Handles gaps (weekends, holidays, halts) gracefully.
"""

import logging
import threading
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class MarketData:
    def __init__(self, alpaca_client):
        self.client = alpaca_client
        self._bar_callbacks: List[Callable] = []
        self._quote_callbacks: List[Callable] = []
        self._bars_cache: Dict[str, pd.DataFrame] = {}
        self._stream = None
        self._stream_thread: Optional[threading.Thread] = None

    def get_historical_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 2000,
    ) -> pd.DataFrame:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        if start is None:
            start = datetime.utcnow() - timedelta(days=limit * 1.5)
        if end is None:
            end = datetime.utcnow()

        tf_map = {
            "1Day": TimeFrame.Day,
            "1Hour": TimeFrame.Hour,
            "5Min": TimeFrame.Minute,
            "1Min": TimeFrame.Minute,
        }
        tf = tf_map.get(timeframe, TimeFrame.Day)

        from alpaca.data.enums import DataFeed
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start,
            end=end,
            limit=limit,
            feed=DataFeed.IEX,
        )
        try:
            bars = self.client.data_client.get_stock_bars(req)
            df = bars.df
            if isinstance(df.index, pd.MultiIndex):
                df = df.xs(symbol, level=0)
            df = df.rename(columns={
                "open": "open", "high": "high", "low": "low",
                "close": "close", "volume": "volume",
            })
            df = df[["open", "high", "low", "close", "volume"]].sort_index()
            df = self._handle_gaps(df)
            self._bars_cache[symbol] = df
            return df
        except Exception as e:
            logger.error(f"get_historical_bars({symbol}) failed: {e}")
            return pd.DataFrame()

    def _handle_gaps(self, df: pd.DataFrame) -> pd.DataFrame:
        """Forward-fill gaps from weekends/holidays/halts."""
        if df.empty:
            return df
        # Normalize to timezone-naive dates so bdate_range aligns correctly
        if hasattr(df.index, "tz") and df.index.tz is not None:
            df.index = df.index.tz_convert("UTC").tz_localize(None)
        df.index = pd.to_datetime(df.index).normalize()
        full_idx = pd.bdate_range(df.index[0], df.index[-1])
        df = df[~df.index.duplicated(keep="last")]
        df = df.reindex(full_idx)
        df["close"] = df["close"].ffill()
        df["open"] = df["open"].ffill()
        df["high"] = df["high"].ffill()
        df["low"] = df["low"].ffill()
        df["volume"] = df["volume"].fillna(0)
        return df.dropna(subset=["close"])

    def get_latest_bar(self, symbol: str) -> Optional[pd.Series]:
        from alpaca.data.requests import StockLatestBarRequest
        from alpaca.data.enums import DataFeed
        try:
            req = StockLatestBarRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)
            result = self.client.data_client.get_stock_latest_bar(req)
            bar = result[symbol]
            return pd.Series({
                "open": bar.open, "high": bar.high,
                "low": bar.low, "close": bar.close, "volume": bar.volume,
            }, name=bar.timestamp)
        except Exception as e:
            logger.error(f"get_latest_bar({symbol}) failed: {e}")
            return None

    def get_latest_quote(self, symbol: str) -> Optional[dict]:
        from alpaca.data.requests import StockLatestQuoteRequest
        from alpaca.data.enums import DataFeed
        try:
            req = StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)
            result = self.client.data_client.get_stock_latest_quote(req)
            q = result[symbol]
            return {"bid": q.bid_price, "ask": q.ask_price, "spread_pct": (q.ask_price - q.bid_price) / q.ask_price}
        except Exception as e:
            logger.error(f"get_latest_quote({symbol}) failed: {e}")
            return None

    def get_snapshot(self, symbol: str) -> Optional[dict]:
        from alpaca.data.requests import StockSnapshotRequest
        from alpaca.data.enums import DataFeed
        try:
            req = StockSnapshotRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)
            result = self.client.data_client.get_stock_snapshot(req)
            snap = result[symbol]
            return {
                "symbol": symbol,
                "latest_trade_price": snap.latest_trade.price,
                "daily_bar": snap.daily_bar,
            }
        except Exception as e:
            logger.error(f"get_snapshot({symbol}) failed: {e}")
            return None

    def subscribe_bars(self, symbols: List[str], timeframe: str, callback: Callable):
        """Subscribe to bar close events via WebSocket."""
        self._bar_callbacks.append(callback)
        self._start_stream(symbols)

    def subscribe_quotes(self, symbols: List[str], callback: Callable):
        self._quote_callbacks.append(callback)

    def _start_stream(self, symbols: List[str]):
        from alpaca.data.live import StockDataStream
        import os

        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        stream = StockDataStream(api_key, secret_key)

        async def _on_bar(bar):
            for cb in self._bar_callbacks:
                try:
                    cb(bar)
                except Exception as e:
                    logger.error(f"Bar callback error: {e}")

        stream.subscribe_bars(_on_bar, *symbols)

        def _run():
            logger.info(f"WebSocket stream started for {symbols}")
            stream.run()

        self._stream = stream
        self._stream_thread = threading.Thread(target=_run, daemon=True)
        self._stream_thread.start()

    def stop_stream(self):
        if self._stream:
            try:
                self._stream.stop()
                logger.info("WebSocket stream stopped")
            except Exception as e:
                logger.warning(f"Error stopping stream: {e}")

    def get_cached_bars(self, symbol: str) -> Optional[pd.DataFrame]:
        return self._bars_cache.get(symbol)
