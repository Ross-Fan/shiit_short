# Altcoin Short Monitoring System

A Python-based system for monitoring cryptocurrency markets (Binance futures) to detect abnormal price pumps and identify short opportunities.

## Features

- **Real-time Market Monitoring**: WebSocket-based monitoring of all perpetual contracts
- **Pump Detection**: Identifies coins with abnormal short-term gains
  - Flash Pump: 5-minute gains > 5%
  - Trend Pump: 1-hour gains > 15%
- **Short Signal Analysis**: Multi-factor confirmation for short opportunities
  - RSI (overbought detection)
  - Relative volume analysis
  - Funding rate monitoring
  - Candlestick pattern recognition (PIN bar, Double Top)
- **Risk Management**: Built-in risk controls including stop-loss and BTC pump protection
- **Configurable**: YAML-based configuration for all parameters

## Installation

1. Clone the repository:
```bash
git clone <repository_url>
cd shiit_short
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Edit `config/config.yaml` to customize parameters:

```yaml
monitor:
  interval_check: 10  # Check every 10 seconds
  min_volume_24h: 50000000  # Minimum 24h volume in USDT

strategy:
  flash_pump_threshold: 0.05  # 5% threshold
  trend_pump_threshold: 0.15  # 15% threshold
  short_rsi: 80  # RSI threshold
  max_positions: 3  # Max concurrent positions

execution:
  leverage: 3  # 3x leverage
  stop_loss: 0.05  # 5% stop loss
  take_profit: 0.10  # 10% take profit
```

## Usage

### Phase 1: Market Monitoring (Current)

Run the monitor in observation mode (no trades):

```bash
python main.py
```

This will:
- Connect to Binance WebSocket (public data, no API key required)
- Monitor all perpetual contracts
- Display pump rankings
- Show short opportunity signals

### Environment Variables

For full functionality including trading (Phase 4), set:

```bash
export BINANCE_API_KEY="your_api_key"
export BINANCE_SECRET_KEY="your_secret_key"
```

### Using Testnet

The system defaults to Binance testnet. To use mainnet, change in `config/config.yaml`:

```yaml
api:
  binance:
    testnet: false
```

## Output Example

```
================================================================================
Altcoin Short Monitoring System
================================================================================
Started at: 2024-04-01 12:00:00
Testnet: True
Flash Pump Threshold: 5.0%
Trend Pump Threshold: 15.0%
RSI Threshold: 80
Max Positions: 3
================================================================================

[12:00:15] === PUMP RANKINGS ===
  1. XYZUSDT     | Type: flash  | 5m:   7.25% | 1h:   8.50% | Vol:  4.52x
  2. ABCUSDT     | Type: trend  | 5m:   3.20% | 1h:  16.80% | Vol:  3.85x

[12:00:20] === SHORT OPPORTUNITIES ===
  XYZUSDT     | Entry: $0.0450 | RSI(1m): 88.5 | RSI(5m): 92.1 | Funding:  0.0250 | Confidence:  85%
       Pattern: Bearish PIN Bar
```

## Project Structure

```
shiit_short/
├── src/
│   ├── __init__.py
│   ├── config_loader.py       # Configuration management
│   ├── data_fetcher.py        # Binance API & WebSocket
│   ├── strategy_engine.py     # Pump detection & signal analysis
│   ├── risk_manager.py        # Risk controls
│   ├── executor.py            # Trade execution (Phase 4)
│   └── indicators.py          # Technical indicators
├── config/
│   └── config.yaml            # Configuration file
├── logs/
├── main.py                    # Main entry point
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Development Roadmap

- **Phase 1**: ✅ Market monitoring and pump detection
- **Phase 2**: Advanced signal analysis and alerts
- **Phase 3**: Backtesting with historical data
- **Phase 4**: Live trading execution

## Risk Warnings

- **Unlimited Upside**: Short positions have unlimited risk if price continues rising
- **Short Squeeze**: Highly pumped coins may experience short squeezes
- **Slippage**: Volatile markets may cause stop-loss slippage
- **Paper Trading**: Always test with paper trading before live trading

## Disclaimer

This software is for educational purposes only. Cryptocurrency trading involves substantial risk of loss. The authors are not responsible for any financial losses incurred while using this system.

## License

MIT License
