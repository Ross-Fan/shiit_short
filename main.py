"""Main entry point for Altcoin Short Monitoring System."""

import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from src.config_loader import Config
from src.data_fetcher import BinanceDataFetcher
from src.strategy_engine import StrategyEngine, PumpSignal, ShortSignal
from src.risk_manager import RiskManager
from src.signal_logger import SignalLogger


class ShortMonitor:
    """Main monitoring application."""

    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize the monitor.

        Args:
            config_path: Path to configuration file
        """
        self.config = Config(config_path)
        self._setup_logging()

        # Initialize components
        self.data_fetcher = BinanceDataFetcher(
            api_key=self.config.get("api", "binance", "api_key"),
            api_secret=self.config.get("api", "binance", "secret_key"),
            testnet=self.config.get("api", "binance", "testnet", default=True),
        )

        self.strategy_engine = StrategyEngine(self.data_fetcher, self.config)
        self.risk_manager = RiskManager(self.data_fetcher, self.config)
        self.signal_logger = SignalLogger(
            log_dir=self.config.get("logging", "signal_log_dir", default="logs/signals")
        )

        # Control flags
        self._running = False
        self._shutdown_requested = False

        # Statistics
        self._check_count = 0
        self._pump_count = 0
        self._signal_count = 0

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        log_level = self.config.get("logging", "level", default="INFO")
        log_file = self.config.get("logging", "file", default="logs/monitor.log")

        # Ensure logs directory exists
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout),
            ],
        )

        self.logger = logging.getLogger("ShortMonitor")

    def _handle_signal(self, signum, frame) -> None:
        """Handle shutdown signals.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        self.logger.info(f"Received signal {signum}, shutting down...")
        self._shutdown_requested = True

    def _on_ticker_update(self, ticker) -> None:
        """Callback for ticker updates (optional).

        Args:
            ticker: Updated ticker data
        """
        # Update position prices if we have a position
        self.risk_manager.update_position_price(ticker.symbol, ticker.price)

    def _print_header(self) -> None:
        """Print monitoring header."""
        print("\n" + "=" * 80)
        print("Altcoin Short Monitoring System")
        print("=" * 80)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Testnet: {self.config.get('api', 'binance', 'testnet', default=True)}")
        print(f"Flash Pump Threshold: {self.config.get('strategy', 'flash_pump_threshold', default=0.05) * 100}%")
        print(f"Trend Pump Threshold: {self.config.get('strategy', 'trend_pump_threshold', default=0.15) * 100}%")
        print(f"RSI Threshold: {self.config.get('strategy', 'short_rsi', default=80)}")
        print(f"Max Positions: {self.config.get('strategy', 'max_positions', default=3)}")
        print("=" * 80 + "\n")

    def _print_pump_rankings(self, pumps: list[PumpSignal]) -> None:
        """Print pump rankings.

        Args:
            pumps: List of pump signals
        """
        if not pumps:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] No pumps detected")
            return

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] === PUMP RANKINGS ===")

        for i, pump in enumerate(pumps[:10], 1):
            print(f"  {i}. {pump.symbol:<12} | "
                  f"Type: {pump.pump_type:<6} | "
                  f"5m: {pump.price_change_5m:>6.2f}% | "
                  f"1h: {pump.price_change_1h:>6.2f}% | "
                  f"Vol: {pump.relative_volume:>5.2f}x")

    def _print_short_signals(self, signals: list[ShortSignal]) -> None:
        """Print short opportunity signals.

        Args:
            signals: List of short signals
        """
        if not signals:
            return

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] === SHORT OPPORTUNITIES ===")

        for signal in signals:
            print(f"  {signal.symbol:<12} | "
                  f"Entry: ${signal.entry_price:.4f} | "
                  f"RSI(1m): {signal.rsi_1m:>5.1f} | "
                  f"RSI(5m): {signal.rsi_5m:>5.1f} | "
                  f"Funding: {signal.funding_rate:>6.2%} | "
                  f"Confidence: {signal.confidence:>4.0%}")

            if signal.pattern:
                print(f"       Pattern: {signal.pattern}")

    def _print_statistics(self) -> None:
        """Print monitoring statistics."""
        print(f"\n--- Statistics ---")
        print(f"  Checks: {self._check_count}")
        print(f"  Pumps detected: {self._pump_count}")
        print(f"  Short signals: {self._signal_count}")

        # Print position status
        exposure = self.risk_manager.get_total_exposure()
        if exposure["position_count"] > 0:
            print(f"  Positions: {exposure['position_count']}")
            print(f"  Total Notional: ${exposure['total_notional']:,.2f}")
            print(f"  Total Margin: ${exposure['total_margin']:,.2f}")
            print(f"  Avg Leverage: {exposure['avg_leverage']:.1f}x")

    def run(self) -> None:
        """Run the monitoring loop."""
        self._print_header()

        # Start WebSocket ticker stream
        self.data_fetcher.add_ticker_callback(self._on_ticker_update)
        self.data_fetcher.start_ticker_stream()

        self.logger.info("Monitor started")
        self._running = True

        interval = self.config.get("monitor", "interval_check", default=10)

        # Wait for initial data to populate
        print("Waiting for market data...")
        for _ in range(10):
            time.sleep(1)
            tickers = self.data_fetcher.get_all_tickers()
            if len(tickers) > 100:
                print(f"Received {len(tickers)} symbols, starting monitoring...")
                break
        else:
            self.logger.warning("Timeout waiting for market data, proceeding anyway")

        try:
            while self._running and not self._shutdown_requested:
                # Wait for data to populate
                time.sleep(1)

                tickers = self.data_fetcher.get_all_tickers()

                if not tickers:
                    self.logger.warning("No ticker data available")
                    continue

                # Detect pumps
                pumps = self.strategy_engine.detect_pumps(tickers)

                if pumps:
                    self._pump_count += len(pumps)
                    self._print_pump_rankings(pumps)

                    # Log all detected pumps
                    self.signal_logger.log_pumps_batch(pumps)

                    # Evaluate short opportunities
                    signals = []
                    for pump in pumps[:5]:  # Check top 5
                        # Risk check
                        risk_check = self.risk_manager.can_open_position(pump.symbol)
                        if not risk_check.allowed:
                            self.logger.info(f"Skip {pump.symbol}: {risk_check.reason}")
                            self.signal_logger.log_risk_rejection(
                                pump.symbol, risk_check.reason, pump
                            )
                            continue

                        signal = self.strategy_engine.evaluate_short_opportunity(pump)
                        if signal:
                            signals.append(signal)
                            self.signal_logger.log_short_signal(signal)
                        else:
                            # Signal evaluated but confidence too low
                            self.signal_logger.log_rejected_signal(
                                pump.symbol, "confidence_below_threshold", pump
                            )

                    if signals:
                        self._signal_count += len(signals)
                        self._print_short_signals(signals)

                # Update statistics
                self._check_count += 1

                # Print statistics every 30 checks
                if self._check_count % 30 == 0:
                    self._print_statistics()

                # Wait for next check interval
                time.sleep(interval - 1)

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}", exc_info=True)
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the monitor."""
        self._running = False
        self.data_fetcher.stop_ticker_stream()

        # Log session summary
        self.signal_logger.log_session_summary()
        session_stats = self.signal_logger.get_session_stats()

        self.logger.info("Monitor stopped")
        print("\n" + "=" * 80)
        print("Monitor stopped")
        print("=" * 80)

        # Print final statistics
        self._print_statistics()

        # Print signal logger stats
        print(f"\n--- Signal Log Stats ---")
        print(f"  Pumps logged: {session_stats['pumps_detected']}")
        print(f"  Signals logged: {session_stats['signals_generated']}")
        print(f"  Rejected signals: {session_stats['signals_rejected']}")
        print(f"  Signal rate: {session_stats['signal_rate']:.2%}")


def main():
    """Main entry point."""
    import os

    # Check for config file argument
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/config.yaml"

    # Verify config file exists
    if not Path(config_path).exists():
        print(f"Error: Configuration file not found: {config_path}")
        print("Please create a config/config.yaml file based on the example.")
        sys.exit(1)

    # Verify API keys are set (either in config or environment)
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")

    if not api_key or not api_secret:
        print("Warning: Binance API keys not set in environment variables.")
        print("For public data monitoring (Phase 1), this is acceptable.")
        print("For trading (Phase 4), set:")
        print("  export BINANCE_API_KEY='your_api_key'")
        print("  export BINANCE_SECRET_KEY='your_secret_key'")
        print()

    # Create and run monitor
    monitor = ShortMonitor(config_path)
    monitor.run()


if __name__ == "__main__":
    main()
