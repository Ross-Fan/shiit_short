架构设计：Altcoin 短期超涨监控与做空策略框架
1. 项目概述
本项目旨在实时监控加密货币市场（以 Binance 为主）中短时间内出现巨大涨幅的 Altcoins，识别潜在的“力竭”信号，并结合技术指标自动化判断做空机会。
2. 核心逻辑流程
全市场扫描： 监控所有永续合约对（USDT 结算）。
异常触发： 识别符合“短时巨涨”定义的币种。
多维确认： 检查成交量、RSI、资金费率及爆仓数据。
执行逻辑： 小仓位试探或结构破坏后入场。
风险对冲： 严格止损与 BTC 环境监测。


3. 模块化设计 (Python 组件)
A. 数据采集模块 (data_fetcher.py)
WebSocket 订阅： 订阅 !ticker@arr 或 !miniTicker@arr 获取全场实时价格。
K线检索： 触发预警后，抓取 1m, 5m, 15m 的历史 K 线计算指标。
深度与订单流： 监控盘口大单分布。
B. 策略引擎模块 (strategy_engine.py)
涨幅过滤逻辑 (Thresholds):
Flash_Pump: 5分钟涨幅 > 5%
Trend_Pump: 1小时涨幅 > 15%
Relative_Volume: 当前 5min 成交量 > 过去 24h 平均 5min 成交量的 3 倍。
做空确认指标:
RSI: 1分钟/5分钟级别 RSI > 85 (严重超买)。
Funding Rate: 资金费率是否正向异常（多头过热）。
M-Top/PIN Bar: 识别 K 线形态是否出现长上影线或双顶结构。
C. 风险控制模块 (risk_manager.py)
硬止损 (Hard Stop): 设定为入场价的 +3% 或前高。
移动止盈 (Trailing Stop): 价格回调至 0.5 斐波那契位时锁定利润。
黑名单设置: 排除新币（刚上线 24h 内）和流动性极差的币种。
BTC 避雷针: 若 BTC 在过去 15 分钟涨幅 > 1%，暂停所有做空操作。
D. 交易执行模块 (executor.py)
API 接口: 对接 binance-connector-python。
下单模式: 建议先使用 LIMIT 订单在拉升的高位挂单，或 MARKET 订单在结构破坏时介入。
杠杆管理: 默认 2x - 5x，严禁高倍。
4. 关键配置参数 (config.yaml)
yaml
monitor:
  interval_check: 10 # 每10秒检查一次
  symbols_type: "PERP" # 仅监控永续合约
  min_volume_24h: 50000000 # 排除日交易量低于 5000万 USDT 的冷门币

strategy:
  pump_threshold: 0.10 # 1小时涨幅达到10%进入观察区
  short_rsi: 80 # RSI 高于此值考虑入场
  max_positions: 3 # 同时持有的最大做空头寸数

execution:
  leverage: 3
  stop_loss: 0.05 # 5% 强制止损
  take_profit: 0.10 # 10% 目标止盈


1. 待开发功能清单 (Roadmap)
Phase 1: 实现全市场 5 分钟涨幅排名轮询脚本。
Phase 2: 在发现“妖币”时推送实时警报， 打印日志。
Phase 3: 编写 Backtrader 插件，回测过去 30 天内做空“超涨币”的胜率。
Phase 4: 实盘对接，加入多阶段分批止盈逻辑。
1. 警告与免责声明
无限拉升风险： Altcoin 可能在没有任何基本面支撑下连续翻倍（Short Squeeze）。
插针风险： 剧烈波动可能导致止损无法在预定价格成交（滑点）。
建议方案： 初期仅使用 纸交易 (Paper Trading) 测试 2 周以上。





