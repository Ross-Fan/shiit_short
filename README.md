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
│   ├── indicators.py          # Technical indicators
│   └── signal_logger.py       # Signal logging for analysis
├── config/
│   └── config.yaml            # Configuration file
├── logs/
│   ├── monitor.log            # Application logs
│   └── signals/               # Signal logs (JSONL format)
│       ├── pumps_YYYYMMDD.jsonl
│       ├── signals_YYYYMMDD.jsonl
│       └── rejected_YYYYMMDD.jsonl
├── main.py                    # Main entry point
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Deployment on Ubuntu Server

### Quick Deploy (One-liner)

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_REPO/shiit_short/main/deploy.sh | bash
```

Or follow the manual steps below:

### Manual Deployment Steps

#### 1. System Prerequisites

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.10+ and pip
sudo apt install -y python3 python3-pip python3-venv git

# Verify Python version (should be 3.10+)
python3 --version
```

#### 2. Clone and Setup

```bash
# Clone repository
cd /opt
sudo git clone https://github.com/YOUR_REPO/shiit_short.git
sudo chown -R $USER:$USER shiit_short
cd shiit_short

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### 3. Configuration

```bash
# Edit configuration
nano config/config.yaml

# Key settings to verify:
# - testnet: false (for real market data)
# - min_volume_24h: adjust based on your preference
# - pump thresholds: adjust as needed
```

#### 4. Create Systemd Service (Recommended)

```bash
# Create service file
sudo tee /etc/systemd/system/shiit-monitor.service > /dev/null << 'EOF'
[Unit]
Description=Altcoin Short Monitoring System
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/shiit_short
Environment=PATH=/opt/shiit_short/venv/bin:/usr/bin
ExecStart=/opt/shiit_short/venv/bin/python main.py
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal

# Resource limits
MemoryLimit=512M

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable shiit-monitor
sudo systemctl start shiit-monitor

# Check status
sudo systemctl status shiit-monitor
```

#### 5. View Logs

```bash
# View systemd service logs (real-time)
sudo journalctl -u shiit-monitor -f

# View application logs
tail -f /opt/shiit_short/logs/monitor.log

# View signal logs
tail -f /opt/shiit_short/logs/signals/pumps_$(date +%Y%m%d).jsonl
tail -f /opt/shiit_short/logs/signals/signals_$(date +%Y%m%d).jsonl
```

#### 6. Service Management

```bash
# Stop service
sudo systemctl stop shiit-monitor

# Restart service
sudo systemctl restart shiit-monitor

# Disable auto-start
sudo systemctl disable shiit-monitor

# View recent logs
sudo journalctl -u shiit-monitor -n 100

# View logs since last boot
sudo journalctl -u shiit-monitor -b
```

### Alternative: Run with Screen/Tmux

If you prefer not to use systemd:

```bash
# Using screen
screen -S shiit
cd /opt/shiit_short
source venv/bin/activate
python main.py
# Press Ctrl+A, D to detach

# Reattach later
screen -r shiit
```

```bash
# Using tmux
tmux new -s shiit
cd /opt/shiit_short
source venv/bin/activate
python main.py
# Press Ctrl+B, D to detach

# Reattach later
tmux attach -t shiit
```

### Log Analysis

Signal logs are in JSONL format for easy analysis:

```bash
# Count pumps detected today
wc -l /opt/shiit_short/logs/signals/pumps_$(date +%Y%m%d).jsonl

# View all short signals
cat /opt/shiit_short/logs/signals/signals_$(date +%Y%m%d).jsonl | jq .

# Filter high-confidence signals (>70%)
cat /opt/shiit_short/logs/signals/signals_*.jsonl | jq 'select(.confidence > 0.7)'

# View rejection reasons
cat /opt/shiit_short/logs/signals/rejected_*.jsonl | jq -r '.reason' | sort | uniq -c | sort -rn
```

### Firewall Configuration (Optional)

The monitor only makes outbound connections, no inbound ports needed:

```bash
# If using UFW, ensure outbound is allowed (default)
sudo ufw status

# The service connects to:
# - wss://fstream.binance.com (WebSocket)
# - https://fapi.binance.com (REST API)
```

### Troubleshooting

**WebSocket connection fails:**
```bash
# Check network connectivity
curl -I https://fapi.binance.com/fapi/v1/ping

# Check DNS resolution
nslookup fstream.binance.com
```

**Service won't start:**
```bash
# Check for errors
sudo journalctl -u shiit-monitor -n 50 --no-pager

# Test manually
cd /opt/shiit_short
source venv/bin/activate
python main.py
```

**High memory usage:**
```bash
# Check memory
free -h

# Restart service to clear memory
sudo systemctl restart shiit-monitor
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
