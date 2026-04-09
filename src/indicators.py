"""Technical indicators module."""

import numpy as np
from typing import Dict, List, Tuple, Optional


class RSI:
    """Relative Strength Index calculator."""

    @staticmethod
    def calculate(prices: List[float], period: int = 14) -> List[float]:
        """Calculate RSI for a series of prices.

        Args:
            prices: List of closing prices
            period: RSI period (default 14)

        Returns:
            List of RSI values
        """
        if len(prices) < period + 1:
            return [np.nan] * len(prices)

        prices = np.array(prices)
        deltas = np.diff(prices)

        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        rsi_values = [np.nan] * period

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))

            rsi_values.append(rsi)

        return rsi_values


class Fibonacci:
    """Fibonacci retracement calculator."""

    @staticmethod
    def calculate_levels(high: float, low: float) -> Dict[str, float]:
        """Calculate Fibonacci retracement levels.

        Args:
            high: Highest price
            low: Lowest price

        Returns:
            Dictionary of Fibonacci levels
        """
        diff = high - low
        levels = {
            "0.0": high,
            "0.236": high - 0.236 * diff,
            "0.382": high - 0.382 * diff,
            "0.5": high - 0.5 * diff,
            "0.618": high - 0.618 * diff,
            "0.786": high - 0.786 * diff,
            "1.0": low,
        }
        return levels

    @staticmethod
    def get_level(high: float, low: float, level: float) -> float:
        """Get specific Fibonacci level.

        Args:
            high: Highest price
            low: Lowest price
            level: Level as percentage (e.g., 0.5 for 50%)

        Returns:
            Price at the Fibonacci level
        """
        return high - level * (high - low)


class CandlePattern:
    """Candlestick pattern recognizer."""

    @staticmethod
    def is_pin_bar(
        open_price: float,
        high: float,
        low: float,
        close: float,
        body_ratio_threshold: float = 0.3,
        wick_ratio_threshold: float = 2.0,
    ) -> Tuple[bool, str]:
        """Check if candle is a PIN bar (long wick, small body).

        Args:
            open_price: Open price
            high: Highest price
            low: Lowest price
            close: Close price
            body_ratio_threshold: Body should be less than this ratio of total range
            wick_ratio_threshold: Wicker should be at least this ratio of body

        Returns:
            Tuple of (is_pin_bar, direction: "bullish" or "bearish")
        """
        total_range = high - low
        if total_range == 0:
            return False, ""

        body_top = max(open_price, close)
        body_bottom = min(open_price, close)
        body_size = body_top - body_bottom

        # Upper wick
        upper_wick = high - body_top
        # Lower wick
        lower_wick = body_bottom - low

        body_ratio = body_size / total_range

        if body_ratio > body_ratio_threshold:
            return False, ""

        # Check for bullish pin (long lower wick)
        if lower_wick > body_size * wick_ratio_threshold and upper_wick < body_size:
            return True, "bullish"

        # Check for bearish pin (long upper wick)
        if upper_wick > body_size * wick_ratio_threshold and lower_wick < body_size:
            return True, "bearish"

        return False, ""

    @staticmethod
    def detect_double_top(
        highs: List[float], tolerance: float = 0.01
    ) -> Tuple[bool, Optional[float]]:
        """Detect double top pattern.

        Args:
            highs: List of recent high prices
            tolerance: Price tolerance for matching tops

        Returns:
            Tuple of (is_double_top, neckline_price)
        """
        if len(highs) < 2:
            return False, None

        # Find local maxima
        peaks = []
        for i in range(1, len(highs) - 1):
            if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
                peaks.append((i, highs[i]))

        if len(peaks) < 2:
            return False, None

        # Check last two peaks
        recent_peaks = peaks[-2:]
        peak1_price = recent_peaks[0][1]
        peak2_price = recent_peaks[1][1]

        if abs(peak2_price - peak1_price) / peak1_price <= tolerance:
            # Find neckline (lowest point between peaks)
            start_idx = recent_peaks[0][0]
            end_idx = recent_peaks[1][0]
            neckline = min(highs[start_idx:end_idx + 1])
            return True, neckline

        return False, None


class VolumeAnalyzer:
    """Volume analysis utilities."""

    @staticmethod
    def calculate_sma_volumes(volumes: List[float], period: int) -> List[float]:
        """Calculate simple moving average of volumes.

        Args:
            volumes: List of volume values
            period: SMA period

        Returns:
            List of SMA values
        """
        if len(volumes) < period:
            return [np.nan] * len(volumes)

        sma_values = []
        for i in range(len(volumes)):
            if i < period - 1:
                sma_values.append(np.nan)
            else:
                sma_values.append(sum(volumes[i - period + 1:i + 1]) / period)

        return sma_values

    @staticmethod
    def is_relative_volume_high(
        current_volume: float, avg_volume: float, multiplier: float = 3.0
    ) -> bool:
        """Check if current volume is relatively high.

        Args:
            current_volume: Current volume
            avg_volume: Average volume
            multiplier: Volume multiplier threshold

        Returns:
            True if volume is above threshold
        """
        if avg_volume == 0:
            return False
        return current_volume > avg_volume * multiplier


class FundingRateAnalyzer:
    """Funding rate analysis utilities."""

    @staticmethod
    def is_funding_rate_high(
        current_rate: float, threshold: float = 0.01
    ) -> bool:
        """Check if funding rate is abnormally high.

        Args:
            current_rate: Current funding rate
            threshold: Threshold (default 1%)

        Returns:
            True if funding rate is high
        """
        return current_rate > threshold

    @staticmethod
    def get_funding_impact(
        funding_rate: float, position_value: float, hours: int = 8
    ) -> float:
        """Calculate funding impact on position.

        Args:
            funding_rate: Current funding rate (as decimal, e.g., 0.01 for 1%)
            position_value: Value of position
            hours: Number of funding periods

        Returns:
            Funding cost or gain (positive = receive, negative = pay)
        """
        return position_value * funding_rate * hours


class MomentumAnalyzer:
    """Momentum exhaustion analyzer for detecting weakening trends."""

    @staticmethod
    def detect_volume_divergence(
        prices: List[float],
        volumes: List[float],
        lookback: int = 10,
    ) -> Tuple[bool, float]:
        """Detect price-volume divergence (price makes new high but volume decreases).

        Args:
            prices: List of closing prices
            volumes: List of volume values
            lookback: Number of periods to look back

        Returns:
            Tuple of (is_divergence, divergence_strength 0-1)
        """
        if len(prices) < lookback or len(volumes) < lookback:
            return False, 0.0

        recent_prices = prices[-lookback:]
        recent_volumes = volumes[-lookback:]

        # Find local price highs
        price_highs = []
        for i in range(1, len(recent_prices) - 1):
            if recent_prices[i] > recent_prices[i - 1] and recent_prices[i] > recent_prices[i + 1]:
                price_highs.append((i, recent_prices[i], recent_volumes[i]))

        if len(price_highs) < 2:
            return False, 0.0

        # Compare the last two highs
        last_high = price_highs[-1]
        prev_high = price_highs[-2]

        # Price higher but volume lower = bearish divergence
        if last_high[1] > prev_high[1] and last_high[2] < prev_high[2]:
            divergence_strength = (prev_high[2] - last_high[2]) / prev_high[2]
            return True, min(divergence_strength, 1.0)

        return False, 0.0

    @staticmethod
    def detect_rsi_divergence(
        prices: List[float],
        rsi_values: List[float],
        lookback: int = 20,
        threshold: float = 5.0,
    ) -> Tuple[bool, str]:
        """Detect RSI bearish divergence (price makes new high but RSI doesn't).

        Args:
            prices: List of closing prices
            rsi_values: List of RSI values
            lookback: Number of periods to look back
            threshold: RSI difference threshold to consider divergence

        Returns:
            Tuple of (is_divergence, description)
        """
        if len(prices) < lookback or len(rsi_values) < lookback:
            return False, ""

        recent_prices = prices[-lookback:]
        recent_rsi = rsi_values[-lookback:]

        # Filter out nan values from RSI
        valid_rsi = [r for r in recent_rsi if not np.isnan(r)]
        if len(valid_rsi) < 5:
            return False, ""

        # Find local maxima in prices
        price_peaks = []
        for i in range(1, len(recent_prices) - 1):
            if recent_prices[i] > recent_prices[i - 1] and recent_prices[i] > recent_prices[i + 1]:
                if not np.isnan(recent_rsi[i]):
                    price_peaks.append((i, recent_prices[i], recent_rsi[i]))

        if len(price_peaks) < 2:
            return False, ""

        # Compare last two price peaks
        last_peak = price_peaks[-1]
        prev_peak = price_peaks[-2]

        # Price higher but RSI lower = bearish divergence
        if last_peak[1] > prev_peak[1] and last_peak[2] < prev_peak[2] - threshold:
            desc = f"RSI divergence: price {last_peak[1]:.4f} > {prev_peak[1]:.4f} but RSI {last_peak[2]:.1f} < {prev_peak[2]:.1f}"
            return True, desc

        return False, ""

    @staticmethod
    def detect_momentum_slowdown(
        price_changes: List[float],
        window: int = 3,
    ) -> Tuple[bool, float]:
        """Detect momentum slowdown (consecutive decreasing gains).

        Args:
            price_changes: List of consecutive period price changes (%)
            window: Number of periods to check

        Returns:
            Tuple of (is_slowing, slowdown_degree 0-1)
        """
        if len(price_changes) < window + 1:
            return False, 0.0

        recent = price_changes[-(window + 1):]

        # Count consecutive decreases
        decreasing_count = 0
        for i in range(1, len(recent)):
            if recent[i] < recent[i - 1]:
                decreasing_count += 1

        # At least window-1 decreases indicate slowdown
        if decreasing_count >= window - 1:
            # Calculate slowdown degree
            if recent[0] > 0:
                slowdown = (recent[0] - recent[-1]) / recent[0]
                return True, min(max(slowdown, 0), 1.0)

        return False, 0.0

    @staticmethod
    def calculate_momentum_score(
        volume_divergence: bool,
        volume_divergence_strength: float,
        rsi_divergence_1m: bool,
        rsi_divergence_5m: bool,
        rsi_divergence_15m: bool,
        momentum_slowdown: bool,
        momentum_slowdown_degree: float,
    ) -> float:
        """Calculate comprehensive exhaustion score.

        Args:
            volume_divergence: Whether volume divergence is detected
            volume_divergence_strength: Strength of volume divergence (0-1)
            rsi_divergence_1m: Whether 1m RSI divergence is detected
            rsi_divergence_5m: Whether 5m RSI divergence is detected
            rsi_divergence_15m: Whether 15m RSI divergence is detected
            momentum_slowdown: Whether momentum slowdown is detected
            momentum_slowdown_degree: Degree of slowdown (0-1)

        Returns:
            Exhaustion score (0-1)
        """
        score = 0.0

        # Volume divergence contributes up to 0.3
        if volume_divergence:
            score += 0.3 * volume_divergence_strength

        # RSI divergences contribute up to 0.5 combined
        if rsi_divergence_1m:
            score += 0.15
        if rsi_divergence_5m:
            score += 0.2
        if rsi_divergence_15m:
            score += 0.15

        # Momentum slowdown contributes up to 0.2
        if momentum_slowdown:
            score += 0.2 * momentum_slowdown_degree

        return min(score, 1.0)
