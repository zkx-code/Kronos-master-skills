# 美股行情与预测入口

美股日线或分钟线请求使用 `scripts/us_market.py`，随后调用原 `scripts/predict.py`。
数据来自 Yahoo Finance，经 yfinance 获取，不是新浪/东方财富 A 股接口。验证具体证券名称、
Yahoo 代码（例如 BRK-B）、USD 计价、交易所、纽约时区和股票/ETF 类型；不接受 OTC、期货、
加密货币或其他市场。支持 NYSE、Nasdaq、NYSE American/Arca 和 BATS 返回的上市市场标识。

## 取数与时间口径

- `--interval 1d` 或 `1/5/15/30/60/120`。常规会话为美东 09:30–16:00，依据 XNYS 日历代理
  所支持美股的常规交易时段。交易所临时变更或个股停牌仍需核验，不声称是 Nasdaq 专用日历。
- 5 分钟普通交易日 78 根，提前收盘日数量减少。没有午休。60 分钟普通日 7 根（最后30分钟），
  120 分钟4根（最后30分钟）；短尾根保留并在 `schedule.csv` 的 `partial_bar` 标记。
  120分钟从完整60分钟源数据聚合OHLC及成交量，跨交易日不合并。
- 日线用交易日零点作为模型时间，分钟线把源开盘标签转换为收盘标签；依据会话实际收盘时间
  排除未完成K线。所有模型时间是纽约当地无时区时间；内部日历处理夏令时。
- 默认 Yahoo 自带OHLC，`auto_adjust=False`，不称其为严格不复权数据；`--adjust auto` 明确
  开启 Yahoo Adj Close 比率调整。保留原始数据、Dividends/Stock Splits，并核对公司行动口径。
- Yahoo不提供真实成交额，必须显式 `--price-only`，后续预测也传相同选项；历史成交量仅在
  `normalized.csv` 保留，模型的量额辅助输出不展示为有效预测。不用价格乘成交量估算成交额。
- 日线请求5年，1分钟请求7天，5/15/30分钟请求1个月，60/120分钟请求2年；这些是请求窗口，
  不保证数据商必定返回足够记录。历史不足、缺根、错误OHLC、网络失败、数据延迟都报错。
  不缩短用户指定lookback、不补行情、不自动换源。可在说明原因后显式调整参数。
- 默认截至实际当前时间；`--as-of` 可指定不晚于现在的纽约当地截止时刻，便于历史留出和
  数据商延迟场景。历史目标价格不输入上下文。仅当前下载数据的截断不证明消除了复权回溯
  或预训练数据泄漏，不能直接声称完成严格历史回测。

## 命令

在现有 Kronos Python 环境安装 `scripts/us-requirements.txt` 的依赖。保持模型依赖与权重。
准备数据（路径用实际技能位置和全新输出目录）：

```powershell
$skill = Join-Path (Get-Location) 'skills/kronos-kline-predict'
$py = Join-Path (Get-Location) '.venv-kronos/Scripts/python.exe'
$prep = 'C:\Users\Lenovo\Documents\Codex\aapl-input-001'
& $py -m pip install -r "$skill\scripts\us-requirements.txt"
& $py "$skill\scripts\us_market.py" --symbol AAPL --interval 5 --lookback 400 --pred-len 20 --price-only --output-dir $prep
& $py "$skill\scripts\predict.py" --csv "$prep\history.csv" --future-csv "$prep\future.csv" --lookback 400 --pred-len 20 --price-only --timezone America/New_York --data-note "$prep\data-source.json" --check-only
```

日线把 `--interval` 改为 `1d`。核验标的和最近完整K线后，预测命令移除 `--check-only`、
追加全新 `--output-dir`，复用既有模型或指定模型/Tokenizer路径。
若用户要求某天全日，依据美股会话计算根数与截止点，不默认用沪深的48根或随意选择日期。

元数据在 `data-source.json`，含代码、市场、源、时区、复权设置、时间范围、源周期、版本、SHA256。
取数脚本只完成单源验证；按 `data.md` 交叉核验后再运行预测，不把来源说明写成已核验却没有证据。
`history.csv`、`future.csv` 可直接交给通用预测器；图表标记纽约时区及短尾根。
不要调用 A 股 `intraday.py summarize`：美股结果按 `schedule.csv` 对齐通用 `forecast.csv`，
依照 SKILL.md 展示图、逐根表格和中文报告。这里只新增行情和时间适配，不修改模型，也未验证美股准确率。

依赖参考：https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html
交易时间参考：https://www.nyse.com/markets/hours-calendars
