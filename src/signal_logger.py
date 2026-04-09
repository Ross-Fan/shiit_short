"""Signal logging module for strategy iteration and analysis."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .strategy_engine import PumpSignal, ShortSignal, ExhaustionSignal


class SignalLogger:
    """Logger for pump detections and short signals.

    Logs are saved in JSON format for easy parsing and analysis.
    """

    def __init__(self, log_dir: str = "logs"):
        """Initialize signal logger.

        Args:
            log_dir: Directory for log files
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Setup file loggers
        self._setup_loggers()

        # Session stats
        self._session_start = datetime.now()
        self._pump_count = 0
        self._signal_count = 0
        self._rejected_count = 0

    def _setup_loggers(self) -> None:
        """Setup separate loggers for different signal types."""
        # Date string for log files
        date_str = datetime.now().strftime("%Y%m%d")

        # Pump detection logger
        self.pump_logger = logging.getLogger("pump_signals")
        self.pump_logger.setLevel(logging.INFO)
        self.pump_logger.handlers.clear()
        pump_handler = logging.FileHandler(
            self.log_dir / f"pumps_{date_str}.jsonl", encoding="utf-8"
        )
        pump_handler.setFormatter(logging.Formatter("%(message)s"))
        self.pump_logger.addHandler(pump_handler)

        # Short signal logger
        self.signal_logger = logging.getLogger("short_signals")
        self.signal_logger.setLevel(logging.INFO)
        self.signal_logger.handlers.clear()
        signal_handler = logging.FileHandler(
            self.log_dir / f"signals_{date_str}.jsonl", encoding="utf-8"
        )
        signal_handler.setFormatter(logging.Formatter("%(message)s"))
        self.signal_logger.addHandler(signal_handler)

        # Rejected signals logger (for analysis)
        self.rejected_logger = logging.getLogger("rejected_signals")
        self.rejected_logger.setLevel(logging.INFO)
        self.rejected_logger.handlers.clear()
        rejected_handler = logging.FileHandler(
            self.log_dir / f"rejected_{date_str}.jsonl", encoding="utf-8"
        )
        rejected_handler.setFormatter(logging.Formatter("%(message)s"))
        self.rejected_logger.addHandler(rejected_handler)

        # Exhaustion signals logger
        self.exhaustion_logger = logging.getLogger("exhaustion_signals")
        self.exhaustion_logger.setLevel(logging.INFO)
        self.exhaustion_logger.handlers.clear()
        exhaustion_handler = logging.FileHandler(
            self.log_dir / f"exhaustion_{date_str}.jsonl", encoding="utf-8"
        )
        exhaustion_handler.setFormatter(logging.Formatter("%(message)s"))
        self.exhaustion_logger.addHandler(exhaustion_handler)

    def log_pump(self, pump: PumpSignal) -> None:
        """Log a detected pump signal.

        Args:
            pump: PumpSignal to log
        """
        self._pump_count += 1

        record = {
            "timestamp": pump.timestamp.isoformat(),
            "type": "pump",
            "symbol": pump.symbol,
            "pump_type": pump.pump_type,
            "gain_from_prev_high": round(pump.gain_from_prev_high, 2),
            "prev_day_high": pump.prev_day_high,
            "current_price": pump.current_price,
            "price_change_5m": round(pump.price_change_5m, 4),
            "price_change_15m": round(pump.price_change_15m, 4),
            "price_change_1h": round(pump.price_change_1h, 4),
            "relative_volume": round(pump.relative_volume, 2),
        }

        self.pump_logger.info(json.dumps(record))

    def log_pumps_batch(self, pumps: List[PumpSignal]) -> None:
        """Log multiple pump signals.

        Args:
            pumps: List of PumpSignal to log
        """
        for pump in pumps:
            self.log_pump(pump)

    def log_short_signal(self, signal: ShortSignal) -> None:
        """Log a short opportunity signal.

        Args:
            signal: ShortSignal to log
        """
        self._signal_count += 1

        record = {
            "timestamp": signal.timestamp.isoformat(),
            "type": "short_signal",
            "symbol": signal.symbol,
            "entry_price": signal.entry_price,
            "pump_type": signal.pump_type,
            "gain_from_prev_high": round(signal.gain_from_prev_high, 2),
            "rsi_1m": round(signal.rsi_1m, 2),
            "rsi_5m": round(signal.rsi_5m, 2),
            "funding_rate": round(signal.funding_rate, 6),
            "volume_multiplier": round(signal.volume_multiplier, 2),
            "pattern": signal.pattern,
            "confidence": round(signal.confidence, 3),
        }

        # Add exhaustion data if available
        if signal.exhaustion:
            record["exhaustion"] = {
                "volume_divergence": signal.exhaustion.volume_divergence,
                "volume_divergence_strength": round(signal.exhaustion.volume_divergence_strength, 3),
                "rsi_divergence_1m": signal.exhaustion.rsi_divergence_1m,
                "rsi_divergence_5m": signal.exhaustion.rsi_divergence_5m,
                "rsi_divergence_15m": signal.exhaustion.rsi_divergence_15m,
                "momentum_slowdown": signal.exhaustion.momentum_slowdown,
                "momentum_slowdown_degree": round(signal.exhaustion.momentum_slowdown_degree, 3),
                "exhaustion_score": round(signal.exhaustion.exhaustion_score, 3),
            }

        self.signal_logger.info(json.dumps(record))

    def log_rejected_signal(
        self,
        symbol: str,
        reason: str,
        pump: Optional[PumpSignal] = None,
        confidence: Optional[float] = None,
    ) -> None:
        """Log a rejected short signal (for analysis).

        Args:
            symbol: Trading pair symbol
            reason: Reason for rejection
            pump: Original pump signal (if available)
            confidence: Confidence score (if calculated)
        """
        self._rejected_count += 1

        record = {
            "timestamp": datetime.now().isoformat(),
            "type": "rejected",
            "symbol": symbol,
            "reason": reason,
        }

        if pump:
            record["pump_type"] = pump.pump_type
            record["gain_from_prev_high"] = round(pump.gain_from_prev_high, 2)
            record["price_change_5m"] = round(pump.price_change_5m, 4)
            record["price_change_1h"] = round(pump.price_change_1h, 4)

        if confidence is not None:
            record["confidence"] = round(confidence, 3)

        self.rejected_logger.info(json.dumps(record))

    def log_exhaustion_signal(self, exhaustion: ExhaustionSignal) -> None:
        """Log an exhaustion signal.

        Args:
            exhaustion: ExhaustionSignal to log
        """
        record = {
            "timestamp": exhaustion.timestamp.isoformat(),
            "type": "exhaustion",
            "symbol": exhaustion.symbol,
            "volume_divergence": exhaustion.volume_divergence,
            "volume_divergence_strength": round(exhaustion.volume_divergence_strength, 3),
            "rsi_divergence_1m": exhaustion.rsi_divergence_1m,
            "rsi_divergence_5m": exhaustion.rsi_divergence_5m,
            "rsi_divergence_15m": exhaustion.rsi_divergence_15m,
            "momentum_slowdown": exhaustion.momentum_slowdown,
            "momentum_slowdown_degree": round(exhaustion.momentum_slowdown_degree, 3),
            "exhaustion_score": round(exhaustion.exhaustion_score, 3),
        }

        self.exhaustion_logger.info(json.dumps(record))

    def log_risk_rejection(
        self, symbol: str, risk_reason: str, pump: Optional[PumpSignal] = None
    ) -> None:
        """Log a risk manager rejection.

        Args:
            symbol: Trading pair symbol
            risk_reason: Risk manager rejection reason
            pump: Original pump signal
        """
        self.log_rejected_signal(
            symbol=symbol,
            reason=f"risk_check: {risk_reason}",
            pump=pump,
        )

    def get_session_stats(self) -> Dict:
        """Get current session statistics.

        Returns:
            Dictionary with session stats
        """
        elapsed = datetime.now() - self._session_start

        return {
            "session_start": self._session_start.isoformat(),
            "elapsed_seconds": int(elapsed.total_seconds()),
            "pumps_detected": self._pump_count,
            "signals_generated": self._signal_count,
            "signals_rejected": self._rejected_count,
            "signal_rate": self._signal_count / self._pump_count if self._pump_count > 0 else 0,
        }

    def log_session_summary(self) -> None:
        """Log session summary to signal logger."""
        stats = self.get_session_stats()
        stats["type"] = "session_summary"
        stats["timestamp"] = datetime.now().isoformat()

        self.signal_logger.info(json.dumps(stats))
