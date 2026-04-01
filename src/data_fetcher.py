"""Data fetcher module for Binance API."""

import json
import time
import threading
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import requests
import websocket
import pandas as pd


@dataclass
class TickerData:
    """Ticker data container."""

    symbol: str
    price: float
    price_change_percent_24h: float
    volume: float
    quote_volume: float
    timestamp: float


@dataclass
class KlineData:
    """K-line data container."""

    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: datetime


class BinanceDataFetcher:
    """Fetches data from Binance API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = False,
    ):
        """Initialize Binance data fetcher.

        Args:
            api_key: Binance API key (optional for public data)
            api_secret: Binance API secret (optional for public data)
            testnet: Use testnet instead of mainnet
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

        if testnet:
            self.base_url = "https://testnet.binance.vision"
            self.ws_url = "wss://testnet.binance.vision/ws"
        else:
            self.base_url = "https://fapi.binance.com"
            self.ws_url = "wss://fstream.binance.com/ws"

        self._ticker_data: Dict[str, TickerData] = {}
        self._callbacks: List[Callable[[TickerData], None]] = []
        self._ws: Optional[websocket.WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._running = False

    def add_ticker_callback(self, callback: Callable[[TickerData], None]) -> None:
        """Add a callback function to be called on ticker updates.

        Args:
            callback: Function that takes TickerData as argument
        """
        self._callbacks.append(callback)

    def start_ticker_stream(self) -> None:
        """Start WebSocket ticker stream."""
        if self._running:
            return

        self._running = True
        self._ws_thread = threading.Thread(target=self._run_ticker_stream, daemon=True)
        self._ws_thread.start()

    def stop_ticker_stream(self) -> None:
        """Stop WebSocket ticker stream."""
        self._running = False
        if self._ws:
            self._ws.close()

        if self._ws_thread:
            self._ws_thread.join(timeout=5)

    def _run_ticker_stream(self) -> None:
        """Run ticker WebSocket in separate thread."""
        def on_message(ws, message):
            data = json.loads(message)

            if not isinstance(data, list):
                return

            for item in data:
                ticker = self._parse_ticker(item)
                if ticker:
                    self._ticker_data[ticker.symbol] = ticker
                    for callback in self._callbacks:
                        try:
                            callback(ticker)
                        except Exception:
                            pass

        def on_error(ws, error):
            print(f"WebSocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            if self._running:
                print("WebSocket closed, reconnecting...")
                time.sleep(5)
                self._run_ticker_stream()

        def on_open(ws):
            print("WebSocket connected")

        self._ws = websocket.WebSocketApp(
            f"{self.ws_url}/!miniTicker@arr",
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open,
        )

        self._ws.run_forever()

    def _parse_ticker(self, data: Dict) -> Optional[TickerData]:
        """Parse ticker data from WebSocket message.

        Args:
            data: Raw ticker data from Binance

        Returns:
            TickerData object or None
        """
        try:
            # Check if it's a perpetual contract
            if not data["s"].endswith("USDT"):
                return None

            return TickerData(
                symbol=data["s"],
                price=float(data["c"]),
                price_change_percent_24h=float(data["P"]),
                volume=float(data["v"]),
                quote_volume=float(data["q"]),
                timestamp=float(data["E"]),
            )
        except (KeyError, ValueError):
            return None

    def get_ticker(self, symbol: str) -> Optional[TickerData]:
        """Get current ticker data for a symbol.

        Args:
            symbol: Trading pair symbol

        Returns:
            TickerData or None
        """
        return self._ticker_data.get(symbol)

    def get_all_tickers(self) -> Dict[str, TickerData]:
        """Get all current ticker data.

        Returns:
            Dictionary of symbol -> TickerData
        """
        return self._ticker_data.copy()

    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 100,
        start_time: Optional[int] = None,
    ) -> List[KlineData]:
        """Fetch k-line data from REST API.

        Args:
            symbol: Trading pair symbol
            interval: K-line interval (1m, 5m, 15m, 1h, etc.)
            limit: Number of k-lines to fetch (max 1500)
            start_time: Start time timestamp in milliseconds

        Returns:
            List of KlineData objects
        """
        endpoint = "/fapi/v1/klines"
        url = f"{self.base_url}{endpoint}"

        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }

        if start_time:
            params["startTime"] = start_time

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            klines = []
            for item in data:
                klines.append(
                    KlineData(
                        open_time=datetime.fromtimestamp(item[0] / 1000),
                        open=float(item[1]),
                        high=float(item[2]),
                        low=float(item[3]),
                        close=float(item[4]),
                        volume=float(item[5]),
                        close_time=datetime.fromtimestamp(item[6] / 1000),
                    )
                )

            return klines

        except requests.RequestException as e:
            print(f"Error fetching klines: {e}")
            return []

    def fetch_klines_df(
        self,
        symbol: str,
        interval: str,
        limit: int = 100,
    ) -> pd.DataFrame:
        """Fetch k-line data as pandas DataFrame.

        Args:
            symbol: Trading pair symbol
            interval: K-line interval
            limit: Number of k-lines to fetch

        Returns:
            DataFrame with OHLCV data
        """
        klines = self.fetch_klines(symbol, interval, limit)

        data = {
            "open_time": [k.open_time for k in klines],
            "open": [k.open for k in klines],
            "high": [k.high for k in klines],
            "low": [k.low for k in klines],
            "close": [k.close for k in klines],
            "volume": [k.volume for k in klines],
        }

        df = pd.DataFrame(data)
        df.set_index("open_time", inplace=True)

        return df

    def fetch_funding_rate(self, symbol: str) -> Optional[float]:
        """Fetch current funding rate for a symbol.

        Args:
            symbol: Trading pair symbol

        Returns:
            Funding rate as decimal or None
        """
        endpoint = "/fapi/v1/premiumIndex"
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.get(url, params={"symbol": symbol}, timeout=10)
            response.raise_for_status()
            data = response.json()

            last_funding_rate = data.get("lastFundingRate")
            if last_funding_rate is not None:
                return float(last_funding_rate)

            return None

        except requests.RequestException as e:
            print(f"Error fetching funding rate: {e}")
            return None

    def fetch_order_book(self, symbol: str, limit: int = 20) -> Optional[Dict]:
        """Fetch current order book depth.

        Args:
            symbol: Trading pair symbol
            limit: Number of bids/asks

        Returns:
            Order book dictionary with 'bids' and 'asks' lists
        """
        endpoint = "/fapi/v1/depth"
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.get(
                url, params={"symbol": symbol, "limit": limit}, timeout=10
            )
            response.raise_for_status()
            data = response.json()

            return {
                "bids": [[float(b[0]), float(b[1])] for b in data.get("bids", [])],
                "asks": [[float(a[0]), float(a[1])] for a in data.get("asks", [])],
            }

        except requests.RequestException as e:
            print(f"Error fetching order book: {e}")
            return None

    def calculate_price_change(
        self, symbol: str, interval: str, periods: int
    ) -> Optional[float]:
        """Calculate price change over specified periods.

        Args:
            symbol: Trading pair symbol
            interval: K-line interval
            periods: Number of periods

        Returns:
            Price change percentage or None
        """
        klines = self.fetch_klines(symbol, interval, periods + 1)

        if len(klines) < periods + 1:
            return None

        start_price = klines[0].close
        end_price = klines[-1].close

        return ((end_price - start_price) / start_price) * 100
