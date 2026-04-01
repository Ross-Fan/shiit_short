"""Risk management module."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta

from .data_fetcher import BinanceDataFetcher
from .indicators import Fibonacci


@dataclass
class Position:
    """Position data."""

    symbol: str
    entry_price: float
    current_price: float
    quantity: float
    leverage: int
    stop_loss: float
    take_profit: float
    entry_time: datetime


@dataclass
class RiskCheck:
    """Risk check result."""

    allowed: bool
    reason: Optional[str] = None


class RiskManager:
    """Risk management for short positions."""

    def __init__(self, data_fetcher: BinanceDataFetcher, config: Dict):
        """Initialize risk manager.

        Args:
            data_fetcher: BinanceDataFetcher instance
            config: Configuration dictionary
        """
        self.data_fetcher = data_fetcher
        self.config = config

        # Load thresholds from config
        self.hard_stop_pct = config.get("execution", "stop_loss", default=0.05)
        self.take_profit_pct = config.get("execution", "take_profit", default=0.10)
        self.max_positions = config.get("strategy", "max_positions", default=3)
        self.btc_pump_threshold = config.get("risk", "btc_pump_threshold", default=0.01)
        self.btc_pump_window = config.get("risk", "btc_pump_window", default=900)  # 15 min

        # Blacklist for new coins and low liquidity
        self.blacklist: Set[str] = set()
        self.blacklisted_symbols: Dict[str, datetime] = {}

        # Current positions
        self.positions: Dict[str, Position] = {}

        # BTC price tracking
        self._btc_start_price: Optional[float] = None
        self._btc_start_time: Optional[datetime] = None

    def can_open_position(self, symbol: str) -> RiskCheck:
        """Check if a new position can be opened.

        Args:
            symbol: Trading pair symbol

        Returns:
            RiskCheck result
        """
        # Check if max positions reached
        if len(self.positions) >= self.max_positions:
            return RiskCheck(allowed=False, reason=f"Max positions ({self.max_positions}) reached")

        # Check if symbol is blacklisted
        if self._is_symbol_blacklisted(symbol):
            return RiskCheck(allowed=False, reason=f"Symbol {symbol} is blacklisted")

        # Check if position already exists
        if symbol in self.positions:
            return RiskCheck(allowed=False, reason=f"Position for {symbol} already exists")

        # Check BTC pump status
        btc_check = self._check_btc_pump()
        if not btc_check.allowed:
            return RiskCheck(allowed=False, reason=f"BTC pump detected: {btc_check.reason}")

        # Check if coin is new (launched within 24h)
        if self._is_new_coin(symbol):
            return RiskCheck(allowed=False, reason=f"Symbol {symbol} is a new coin (< 24h)")

        return RiskCheck(allowed=True)

    def calculate_position_levels(
        self, entry_price: float, symbol: str
    ) -> Dict[str, float]:
        """Calculate stop loss and take profit levels.

        Args:
            entry_price: Entry price
            symbol: Trading pair symbol

        Returns:
            Dictionary with levels (stop_loss, take_profit, trailing_stop)
        """
        # Get recent price action for structure-based stop
        klines = self.data_fetcher.fetch_klines(symbol, "15m", 30)

        if klines:
            recent_high = max([k.high for k in klines[-20:]])
            structure_stop = recent_high * 1.005  # Slightly above recent high
        else:
            structure_stop = entry_price * 1.05

        # Hard stop (whichever is higher)
        hard_stop = max(
            entry_price * (1 + self.hard_stop_pct),
            structure_stop
        )

        # Take profit
        take_profit = entry_price * (1 - self.take_profit_pct)

        # Initial trailing stop (at 50% Fib level)
        if klines:
            low_20 = min([k.low for k in klines[-20:]])
            trailing_stop = Fibonacci.get_level(recent_high, low_20, 0.5)
        else:
            trailing_stop = entry_price

        return {
            "stop_loss": hard_stop,
            "take_profit": take_profit,
            "trailing_stop": trailing_stop,
        }

    def open_position(
        self,
        symbol: str,
        entry_price: float,
        quantity: float,
        leverage: int,
    ) -> Position:
        """Open a new short position.

        Args:
            symbol: Trading pair symbol
            entry_price: Entry price
            quantity: Position size
            leverage: Leverage multiplier

        Returns:
            Position object
        """
        levels = self.calculate_position_levels(entry_price, symbol)

        position = Position(
            symbol=symbol,
            entry_price=entry_price,
            current_price=entry_price,
            quantity=quantity,
            leverage=leverage,
            stop_loss=levels["stop_loss"],
            take_profit=levels["take_profit"],
            entry_time=datetime.now(),
        )

        self.positions[symbol] = position
        return position

    def close_position(self, symbol: str) -> Optional[Position]:
        """Close a position.

        Args:
            symbol: Trading pair symbol

        Returns:
            Closed Position or None
        """
        return self.positions.pop(symbol, None)

    def update_position_price(self, symbol: str, current_price: float) -> None:
        """Update current price for a position.

        Args:
            symbol: Trading pair symbol
            current_price: Current price
        """
        if symbol in self.positions:
            self.positions[symbol].current_price = current_price

    def check_position_triggers(self, symbol: str) -> Dict[str, bool]:
        """Check if position triggers are hit.

        Args:
            symbol: Trading pair symbol

        Returns:
            Dictionary with trigger flags (stop_loss, take_profit, trailing)
        """
        if symbol not in self.positions:
            return {}

        position = self.positions[symbol]
        current_price = position.current_price

        triggers = {
            "stop_loss": current_price >= position.stop_loss,
            "take_profit": current_price <= position.take_profit,
        }

        return triggers

    def update_trailing_stop(self, symbol: str, current_price: float) -> Optional[float]:
        """Update trailing stop based on current price.

        Args:
            symbol: Trading pair symbol
            current_price: Current price

        Returns:
            New trailing stop or None
        """
        if symbol not in self.positions:
            return None

        position = self.positions[symbol]

        # Calculate new trailing stop at 50% Fib level if price dropped
        entry = position.entry_price
        current = current_price

        if current < entry:
            dropped_pct = (entry - current) / entry

            # If dropped more than 50% of target, update trailing stop
            if dropped_pct > self.take_profit_pct * 0.5:
                new_trailing = entry - (entry - current) * 0.5
                position.stop_loss = min(position.stop_loss, new_trailing)
                return new_trailing

        return None

    def add_to_blacklist(self, symbol: str, duration: Optional[int] = None) -> None:
        """Add symbol to blacklist.

        Args:
            symbol: Trading pair symbol
            duration: Duration in hours (None = permanent)
        """
        if duration:
            expiry = datetime.now() + timedelta(hours=duration)
            self.blacklisted_symbols[symbol] = expiry
        else:
            self.blacklist.add(symbol)

    def remove_from_blacklist(self, symbol: str) -> None:
        """Remove symbol from blacklist.

        Args:
            symbol: Trading pair symbol
        """
        self.blacklist.discard(symbol)
        self.blacklisted_symbols.pop(symbol, None)

    def _is_symbol_blacklisted(self, symbol: str) -> bool:
        """Check if symbol is blacklisted.

        Args:
            symbol: Trading pair symbol

        Returns:
            True if blacklisted
        """
        if symbol in self.blacklist:
            return True

        # Check temporary blacklist
        if symbol in self.blacklisted_symbols:
            expiry = self.blacklisted_symbols[symbol]
            if datetime.now() >= expiry:
                self.remove_from_blacklist(symbol)
                return False
            return True

        return False

    def _is_new_coin(self, symbol: str) -> bool:
        """Check if coin is newly listed (within 24h).

        Args:
            symbol: Trading pair symbol

        Returns:
            True if new coin
        """
        klines = self.data_fetcher.fetch_klines(symbol, "1d", 5)

        if not klines or len(klines) < 2:
            return True

        # If first kline open time is within 24h, it's new
        first_open = klines[0].open_time
        return (datetime.now() - first_open) < timedelta(hours=24)

    def _check_btc_pump(self) -> RiskCheck:
        """Check if BTC is pumping (market-wide rally).

        Returns:
            RiskCheck result
        """
        ticker = self.data_fetcher.get_ticker("BTCUSDT")

        if not ticker:
            return RiskCheck(allowed=True)

        current_price = ticker.price
        now = datetime.now()

        # Initialize BTC tracking
        if self._btc_start_price is None:
            self._btc_start_price = current_price
            self._btc_start_time = now
            return RiskCheck(allowed=True)

        # Check if window expired
        time_since_start = (now - self._btc_start_time).total_seconds()
        if time_since_start > self.btc_pump_window:
            self._btc_start_price = current_price
            self._btc_start_time = now
            return RiskCheck(allowed=True)

        # Calculate change
        change_pct = (current_price - self._btc_start_price) / self._btc_start_price

        if change_pct > self.btc_pump_threshold:
            return RiskCheck(
                allowed=False,
                reason=f"BTC up {change_pct:.2%} in {int(time_since_start / 60)}min"
            )

        return RiskCheck(allowed=True)

    def get_position_pnl(self, symbol: str) -> Optional[float]:
        """Get current PnL for a position.

        Args:
            symbol: Trading pair symbol

        Returns:
            PnL as percentage or None
        """
        if symbol not in self.positions:
            return None

        position = self.positions[symbol]
        entry = position.entry_price
        current = position.current_price
        leverage = position.leverage

        pnl_pct = ((entry - current) / entry) * leverage * 100
        return pnl_pct

    def get_total_exposure(self) -> Dict[str, float]:
        """Get total exposure statistics.

        Returns:
            Dictionary with exposure metrics
        """
        total_notional = 0.0
        total_margin = 0.0

        for position in self.positions.values():
            notional = position.current_price * position.quantity
            margin = notional / position.leverage
            total_notional += notional
            total_margin += margin

        return {
            "total_notional": total_notional,
            "total_margin": total_margin,
            "position_count": len(self.positions),
            "avg_leverage": sum(p.leverage for p in self.positions.values()) / len(self.positions)
            if self.positions else 0,
        }
