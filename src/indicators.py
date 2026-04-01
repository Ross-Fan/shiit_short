"""Technical indicators module."""

import numpy as np
from typing import List, Tuple, Optional


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
