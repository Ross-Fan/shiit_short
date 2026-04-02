"""Strategy engine module for short signal detection."""

from dataclasses import dataclass
from typing import Dict, List, Optional, TYPE_CHECKING
import pandas as pd
from datetime import datetime, timedelta

from .data_fetcher import BinanceDataFetcher, TickerData
from .indicators import RSI, Fibonacci, CandlePattern, VolumeAnalyzer, FundingRateAnalyzer

if TYPE_CHECKING:
    from .config_loader import Config


@dataclass
class PumpSignal:
    """Pump detection signal."""

    symbol: str
    pump_type: str  # "flash" or "trend"
    price_change_5m: float
    price_change_1h: float
    relative_volume: float
    timestamp: datetime


@dataclass
class ShortSignal:
    """Short opportunity signal."""

    symbol: str
    entry_price: float
    rsi_1m: float
    rsi_5m: float
    funding_rate: float
    volume_multiplier: float
    pattern: Optional[str]  # PIN bar, M-Top, etc.
    confidence: float  # 0.0 to 1.0
    timestamp: datetime


class StrategyEngine:
    """Engine for detecting short opportunities."""

    def __init__(self, data_fetcher: BinanceDataFetcher, config: "Config"):
        """Initialize strategy engine.

        Args:
            data_fetcher: BinanceDataFetcher instance
            config: Config instance
        """
        self.data_fetcher = data_fetcher
        self.config = config

        # Load thresholds from config
        self.flash_pump_threshold = config.get("strategy", "flash_pump_threshold", default=0.05)
        self.trend_pump_threshold = config.get("strategy", "trend_pump_threshold", default=0.15)
        self.volume_multiplier = config.get("strategy", "volume_multiplier", default=3.0)
        self.rsi_short_threshold = config.get("strategy", "short_rsi", default=80)
        self.min_volume_24h = config.get("monitor", "min_volume_24h", default=50000000)

        # Initialize indicators
        self.rsi_calculator = RSI()
        self.fibonacci = Fibonacci()
        self.pattern_recognizer = CandlePattern()
        self.volume_analyzer = VolumeAnalyzer()
        self.funding_analyzer = FundingRateAnalyzer()

        # Cache for price change calculations
        self._price_change_cache: Dict[str, Dict[str, float]] = {}
        self._last_cache_update: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(seconds=30)

    def detect_pumps(self, tickers: Dict[str, TickerData]) -> List[PumpSignal]:
        """Detect coins with abnormal price pumps.

        Args:
            tickers: Dictionary of symbol -> TickerData

        Returns:
            List of PumpSignal objects
        """
        pumps = []

        for symbol, ticker in tickers.items():
            # Filter by 24h volume
            if ticker.quote_volume < self.min_volume_24h:
                continue

            # Get price changes
            changes = self._get_price_changes(symbol)

            if changes is None:
                continue

            price_change_5m = changes.get("5m", 0)
            price_change_1h = changes.get("1h", 0)

            pump_type = None

            # Check for flash pump
            if price_change_5m >= self.flash_pump_threshold * 100:
                pump_type = "flash"

            # Check for trend pump
            elif price_change_1h >= self.trend_pump_threshold * 100:
                pump_type = "trend"

            if pump_type:
                # Calculate relative volume
                rel_volume = self._calculate_relative_volume(symbol)

                pump = PumpSignal(
                    symbol=symbol,
                    pump_type=pump_type,
                    price_change_5m=price_change_5m,
                    price_change_1h=price_change_1h,
                    relative_volume=rel_volume,
                    timestamp=datetime.now(),
                )

                pumps.append(pump)

        # Sort by total pump (5m + 1h combined weight)
        pumps.sort(
            key=lambda x: (x.price_change_5m * 2 + x.price_change_1h),
            reverse=True,
        )

        return pumps

    def evaluate_short_opportunity(self, pump: PumpSignal) -> Optional[ShortSignal]:
        """Evaluate if a pumped coin is a good short opportunity.

        Args:
            pump: PumpSignal to evaluate

        Returns:
            ShortSignal or None
        """
        symbol = pump.symbol
        ticker = self.data_fetcher.get_ticker(symbol)

        if not ticker:
            return None

        # Get k-lines for analysis
        klines_1m = self.data_fetcher.fetch_klines(symbol, "1m", 60)
        klines_5m = self.data_fetcher.fetch_klines(symbol, "5m", 60)

        if not klines_1m or not klines_5m:
            return None

        # Calculate RSI
        closes_1m = [k.close for k in klines_1m]
        closes_5m = [k.close for k in klines_5m]

        rsi_values_1m = self.rsi_calculator.calculate(closes_1m, period=14)
        rsi_values_5m = self.rsi_calculator.calculate(closes_5m, period=14)

        rsi_1m = rsi_values_1m[-1] if not all(pd.isna(rsi_values_1m)) else 0
        rsi_5m = rsi_values_5m[-1] if not all(pd.isna(rsi_values_5m)) else 0

        # Get funding rate
        funding_rate = self.data_fetcher.fetch_funding_rate(symbol)
        if funding_rate is None:
            funding_rate = 0

        # Check candle patterns
        last_kline = klines_1m[-1]
        is_pin_bar, pin_direction = self.pattern_recognizer.is_pin_bar(
            last_kline.open,
            last_kline.high,
            last_kline.low,
            last_kline.close,
        )

        pattern = None
        if is_pin_bar and pin_direction == "bearish":
            pattern = "Bearish PIN Bar"

        # Check for double top
        highs = [k.high for k in klines_5m[-30:]]
        is_double_top, neckline = self.pattern_recognizer.detect_double_top(highs)
        if is_double_top:
            pattern = f"Double Top (neckline: {neckline:.4f})"

        # Calculate confidence score
        confidence = self._calculate_confidence(
            pump, rsi_1m, rsi_5m, funding_rate, pump.relative_volume, pattern is not None
        )

        # Only return if confidence is above threshold
        if confidence >= 0.5:
            return ShortSignal(
                symbol=symbol,
                entry_price=ticker.price,
                rsi_1m=rsi_1m,
                rsi_5m=rsi_5m,
                funding_rate=funding_rate,
                volume_multiplier=pump.relative_volume,
                pattern=pattern,
                confidence=confidence,
                timestamp=datetime.now(),
            )

        return None

    def _calculate_confidence(
        self,
        pump: PumpSignal,
        rsi_1m: float,
        rsi_5m: float,
        funding_rate: float,
        relative_volume: float,
        has_pattern: bool,
    ) -> float:
        """Calculate confidence score for short opportunity.

        Args:
            pump: PumpSignal data
            rsi_1m: 1-minute RSI
            rsi_5m: 5-minute RSI
            funding_rate: Funding rate
            relative_volume: Relative volume multiplier
            has_pattern: Whether a bearish pattern was detected

        Returns:
            Confidence score (0.0 to 1.0)
        """
        score = 0.0

        # RSI score (up to 0.3)
        if rsi_1m > 90:
            score += 0.3
        elif rsi_1m > self.rsi_short_threshold:
            score += 0.25

        if rsi_5m > 85:
            score += 0.2
        elif rsi_5m > self.rsi_short_threshold:
            score += 0.15

        # Funding rate score (up to 0.2)
        if funding_rate > 0.05:  # > 5%
            score += 0.2
        elif funding_rate > 0.01:  # > 1%
            score += 0.15

        # Volume score (up to 0.2)
        if relative_volume > 5:
            score += 0.2
        elif relative_volume > self.volume_multiplier:
            score += 0.15

        # Pattern score (up to 0.15)
        if has_pattern:
            score += 0.15

        # Pump type bonus (up to 0.15)
        if pump.pump_type == "flash":
            score += 0.1
        elif pump.pump_type == "trend":
            score += 0.05

        return min(score, 1.0)

    def _get_price_changes(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get cached or calculate price changes for a symbol.

        Args:
            symbol: Trading pair symbol

        Returns:
            Dictionary with price changes
        """
        now = datetime.now()
        last_update = self._last_cache_update.get(symbol)

        if last_update and (now - last_update) < self._cache_ttl:
            return self._price_change_cache.get(symbol)

        # Calculate changes
        change_5m = self.data_fetcher.calculate_price_change(symbol, "5m", 1)
        change_15m = self.data_fetcher.calculate_price_change(symbol, "15m", 1)
        change_1h = self.data_fetcher.calculate_price_change(symbol, "1h", 1)

        if change_5m is None or change_15m is None or change_1h is None:
            return None

        changes = {
            "5m": change_5m,
            "15m": change_15m,
            "1h": change_1h,
        }

        self._price_change_cache[symbol] = changes
        self._last_cache_update[symbol] = now

        return changes

    def _calculate_relative_volume(self, symbol: str) -> float:
        """Calculate relative volume (current / 24h average).

        Args:
            symbol: Trading pair symbol

        Returns:
            Volume multiplier
        """
        klines_5m = self.data_fetcher.fetch_klines(symbol, "5m", 300)  # 25 hours

        if not klines_5m:
            return 0.0

        volumes = [k.volume for k in klines_5m]
        current_volume = volumes[-1]

        # Calculate average over last 24h (excluding current)
        avg_volume_24h = sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) > 1 else 0

        if avg_volume_24h == 0:
            return 0.0

        return current_volume / avg_volume_24h

    def calculate_stop_loss_levels(self, entry_price: float, klines: List) -> Dict[str, float]:
        """Calculate stop loss levels based on price action.

        Args:
            entry_price: Entry price
            klines: List of recent k-line data

        Returns:
            Dictionary with stop loss levels
        """
        recent_high = max([k.high for k in klines[-20:]])

        return {
            "hard_stop": entry_price * 1.03,  # +3%
            "structure_stop": recent_high,
            "fib_618": self.fibonacci.get_level(recent_high, min([k.low for k in klines[-20:]]), 0.618),
        }
