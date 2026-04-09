"""Strategy engine module for short signal detection."""

from dataclasses import dataclass
from typing import Dict, List, Optional, TYPE_CHECKING
import pandas as pd
from datetime import datetime, timedelta

from .data_fetcher import BinanceDataFetcher, TickerData
from .indicators import RSI, Fibonacci, CandlePattern, VolumeAnalyzer, FundingRateAnalyzer, MomentumAnalyzer

if TYPE_CHECKING:
    from .config_loader import Config


@dataclass
class PumpSignal:
    """Pump detection signal."""

    symbol: str
    pump_type: str  # "moderate"(50-100%) / "extreme"(100-200%) / "ultra"(200%+)
    gain_from_prev_high: float  # Gain from previous day's high (%)
    price_change_5m: float  # 5-minute price change (%)
    price_change_15m: float  # 15-minute price change (%)
    price_change_1h: float  # 1-hour price change (%)
    relative_volume: float  # Volume multiplier
    prev_day_high: float  # Previous day's high price
    current_price: float  # Current price
    timestamp: datetime


@dataclass
class ExhaustionSignal:
    """Momentum exhaustion signal."""

    symbol: str
    volume_divergence: bool  # Price-volume divergence detected
    volume_divergence_strength: float  # Divergence strength (0-1)
    rsi_divergence_1m: bool  # 1-minute RSI divergence
    rsi_divergence_5m: bool  # 5-minute RSI divergence
    rsi_divergence_15m: bool  # 15-minute RSI divergence
    momentum_slowdown: bool  # Momentum slowdown detected
    momentum_slowdown_degree: float  # Slowdown degree (0-1)
    exhaustion_score: float  # Combined exhaustion score (0-1)
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
    pump_type: str  # From PumpSignal
    gain_from_prev_high: float  # From PumpSignal
    exhaustion: Optional[ExhaustionSignal]  # Exhaustion signal
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

        # Load pump thresholds from config (relative to previous day's high)
        self.pump_threshold_moderate = config.get(
            "strategy", "pump_thresholds", "moderate", default=0.50
        )
        self.pump_threshold_extreme = config.get(
            "strategy", "pump_thresholds", "extreme", default=1.00
        )
        self.pump_threshold_ultra = config.get(
            "strategy", "pump_thresholds", "ultra", default=2.00
        )

        # Load other thresholds
        self.volume_multiplier = config.get("strategy", "volume_multiplier", default=3.0)
        self.rsi_short_threshold = config.get("strategy", "short_rsi", default=80)
        self.min_volume_24h = config.get("monitor", "min_volume_24h", default=50000000)
        self.min_confidence = config.get("strategy", "min_confidence", default=0.6)

        # Exhaustion detection parameters
        self.vol_div_lookback = config.get(
            "strategy", "exhaustion", "volume_divergence_lookback", default=10
        )
        self.rsi_div_threshold = config.get(
            "strategy", "exhaustion", "rsi_divergence_threshold", default=5
        )
        self.mom_slowdown_window = config.get(
            "strategy", "exhaustion", "momentum_slowdown_window", default=3
        )

        # Initialize indicators
        self.rsi_calculator = RSI()
        self.fibonacci = Fibonacci()
        self.pattern_recognizer = CandlePattern()
        self.volume_analyzer = VolumeAnalyzer()
        self.funding_analyzer = FundingRateAnalyzer()
        self.momentum_analyzer = MomentumAnalyzer()

        # Cache for price change calculations (short-term, 30s TTL)
        self._price_change_cache: Dict[str, Dict[str, float]] = {}
        self._last_cache_update: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(seconds=30)

        # Cache for daily high data (long-term, 6h TTL)
        self._daily_cache: Dict[str, Dict] = {}
        self._daily_cache_ttl = timedelta(hours=6)

    def detect_pumps(self, tickers: Dict[str, TickerData]) -> List[PumpSignal]:
        """Detect coins with abnormal price pumps relative to previous day's high.

        Args:
            tickers: Dictionary of symbol -> TickerData

        Returns:
            List of PumpSignal objects sorted by gain percentage
        """
        pumps = []

        for symbol, ticker in tickers.items():
            # Filter by 24h volume
            if ticker.quote_volume < self.min_volume_24h:
                continue

            # Get previous day's high price
            daily_data = self._get_prev_day_high(symbol)
            if daily_data is None:
                continue

            prev_day_high = daily_data["prev_high"]
            current_price = ticker.price

            # Calculate gain from previous day's high
            if prev_day_high <= 0:
                continue
            gain_pct = ((current_price - prev_day_high) / prev_day_high) * 100

            # Classify by gain level
            if gain_pct >= self.pump_threshold_ultra * 100:
                pump_type = "ultra"  # 200%+
            elif gain_pct >= self.pump_threshold_extreme * 100:
                pump_type = "extreme"  # 100-200%
            elif gain_pct >= self.pump_threshold_moderate * 100:
                pump_type = "moderate"  # 50-100%
            else:
                continue  # Below threshold, skip

            # Get short-term price changes for momentum analysis
            changes = self._get_price_changes(symbol)

            # Calculate relative volume
            rel_volume = self._calculate_relative_volume(symbol)

            pump = PumpSignal(
                symbol=symbol,
                pump_type=pump_type,
                gain_from_prev_high=gain_pct,
                price_change_5m=changes.get("5m", 0) if changes else 0,
                price_change_15m=changes.get("15m", 0) if changes else 0,
                price_change_1h=changes.get("1h", 0) if changes else 0,
                relative_volume=rel_volume,
                prev_day_high=prev_day_high,
                current_price=current_price,
                timestamp=datetime.now(),
            )

            pumps.append(pump)

        # Sort by gain from previous day's high (highest first)
        pumps.sort(key=lambda x: x.gain_from_prev_high, reverse=True)

        return pumps

    def _get_prev_day_high(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get previous day's high price with caching (6h TTL).

        Args:
            symbol: Trading pair symbol

        Returns:
            Dictionary with 'prev_high' or None
        """
        cache_key = f"daily_{symbol}"
        now = datetime.now()

        # Check cache
        if cache_key in self._daily_cache:
            cached = self._daily_cache[cache_key]
            if (now - cached["time"]) < self._daily_cache_ttl:
                return cached["data"]

        # Fetch daily klines (need 2 to get previous day)
        klines = self.data_fetcher.fetch_klines(symbol, "1d", 2)
        if not klines or len(klines) < 2:
            return None

        # First kline is the previous completed day
        data = {"prev_high": klines[0].high}
        self._daily_cache[cache_key] = {"time": now, "data": data}
        return data

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
        klines_15m = self.data_fetcher.fetch_klines(symbol, "15m", 30)

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

        # Evaluate exhaustion signals
        exhaustion = self.evaluate_exhaustion(
            pump, klines_1m, klines_5m, klines_15m,
            rsi_values_1m, rsi_values_5m
        )

        # Calculate confidence score with exhaustion
        confidence = self._calculate_confidence(
            pump, rsi_1m, rsi_5m, funding_rate,
            pump.relative_volume, pattern is not None, exhaustion
        )

        # Only return if confidence is above threshold
        if confidence >= self.min_confidence:
            return ShortSignal(
                symbol=symbol,
                entry_price=ticker.price,
                rsi_1m=rsi_1m,
                rsi_5m=rsi_5m,
                funding_rate=funding_rate,
                volume_multiplier=pump.relative_volume,
                pattern=pattern,
                confidence=confidence,
                pump_type=pump.pump_type,
                gain_from_prev_high=pump.gain_from_prev_high,
                exhaustion=exhaustion,
                timestamp=datetime.now(),
            )

        return None

    def evaluate_exhaustion(
        self,
        pump: PumpSignal,
        klines_1m: List,
        klines_5m: List,
        klines_15m: Optional[List],
        rsi_values_1m: List[float],
        rsi_values_5m: List[float],
    ) -> Optional[ExhaustionSignal]:
        """Evaluate momentum exhaustion signals.

        Args:
            pump: PumpSignal being evaluated
            klines_1m: 1-minute klines
            klines_5m: 5-minute klines
            klines_15m: 15-minute klines (optional)
            rsi_values_1m: Pre-calculated 1m RSI values
            rsi_values_5m: Pre-calculated 5m RSI values

        Returns:
            ExhaustionSignal or None
        """
        symbol = pump.symbol

        # Extract prices and volumes
        prices_1m = [k.close for k in klines_1m]
        volumes_1m = [k.volume for k in klines_1m]
        prices_5m = [k.close for k in klines_5m]
        volumes_5m = [k.volume for k in klines_5m]

        # 1. Volume divergence detection (using 5m data)
        vol_div, vol_div_strength = self.momentum_analyzer.detect_volume_divergence(
            prices_5m, volumes_5m, lookback=self.vol_div_lookback
        )

        # 2. RSI divergence detection across multiple timeframes
        rsi_div_1m, _ = self.momentum_analyzer.detect_rsi_divergence(
            prices_1m, rsi_values_1m, lookback=20, threshold=self.rsi_div_threshold
        )
        rsi_div_5m, _ = self.momentum_analyzer.detect_rsi_divergence(
            prices_5m, rsi_values_5m, lookback=20, threshold=self.rsi_div_threshold
        )

        rsi_div_15m = False
        if klines_15m and len(klines_15m) >= 20:
            prices_15m = [k.close for k in klines_15m]
            rsi_values_15m = self.rsi_calculator.calculate(prices_15m, period=14)
            rsi_div_15m, _ = self.momentum_analyzer.detect_rsi_divergence(
                prices_15m, rsi_values_15m, lookback=20, threshold=self.rsi_div_threshold
            )

        # 3. Momentum slowdown detection (using 5m consecutive price changes)
        price_changes_5m = []
        for i in range(1, min(6, len(klines_5m))):
            if klines_5m[-i - 1].close > 0:
                change = (klines_5m[-i].close - klines_5m[-i - 1].close) / klines_5m[-i - 1].close * 100
                price_changes_5m.insert(0, change)

        mom_slowdown, mom_degree = self.momentum_analyzer.detect_momentum_slowdown(
            price_changes_5m, window=self.mom_slowdown_window
        )

        # 4. Calculate exhaustion score
        exhaustion_score = self.momentum_analyzer.calculate_momentum_score(
            vol_div, vol_div_strength,
            rsi_div_1m, rsi_div_5m, rsi_div_15m,
            mom_slowdown, mom_degree
        )

        return ExhaustionSignal(
            symbol=symbol,
            volume_divergence=vol_div,
            volume_divergence_strength=vol_div_strength,
            rsi_divergence_1m=rsi_div_1m,
            rsi_divergence_5m=rsi_div_5m,
            rsi_divergence_15m=rsi_div_15m,
            momentum_slowdown=mom_slowdown,
            momentum_slowdown_degree=mom_degree,
            exhaustion_score=exhaustion_score,
            timestamp=datetime.now(),
        )

    def _calculate_confidence(
        self,
        pump: PumpSignal,
        rsi_1m: float,
        rsi_5m: float,
        funding_rate: float,
        relative_volume: float,
        has_pattern: bool,
        exhaustion: Optional[ExhaustionSignal] = None,
    ) -> float:
        """Calculate confidence score for short opportunity.

        Args:
            pump: PumpSignal data
            rsi_1m: 1-minute RSI
            rsi_5m: 5-minute RSI
            funding_rate: Funding rate
            relative_volume: Relative volume multiplier
            has_pattern: Whether a bearish pattern was detected
            exhaustion: Optional exhaustion signal

        Returns:
            Confidence score (0.0 to 1.0)
        """
        score = 0.0

        # RSI score (up to 0.25)
        if rsi_1m > 90:
            score += 0.15
        elif rsi_1m > self.rsi_short_threshold:
            score += 0.1

        if rsi_5m > 85:
            score += 0.1
        elif rsi_5m > self.rsi_short_threshold:
            score += 0.05

        # Funding rate score (up to 0.1)
        if funding_rate > 0.05:  # > 5%
            score += 0.1
        elif funding_rate > 0.01:  # > 1%
            score += 0.05

        # Volume score (up to 0.1)
        if relative_volume > 5:
            score += 0.1
        elif relative_volume > self.volume_multiplier:
            score += 0.05

        # Pattern score (up to 0.1)
        if has_pattern:
            score += 0.1

        # Pump type bonus based on gain level (up to 0.15)
        if pump.pump_type == "ultra":  # 200%+
            score += 0.15
        elif pump.pump_type == "extreme":  # 100-200%
            score += 0.1
        elif pump.pump_type == "moderate":  # 50-100%
            score += 0.05

        # Exhaustion signal bonus (up to 0.3)
        if exhaustion:
            score += exhaustion.exhaustion_score * 0.3

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
