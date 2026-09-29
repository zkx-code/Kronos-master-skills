# 港股行情与预测

港股预测使用 `scripts/hk_market.py` 准备数据，随后复用 `scripts/predict.py` 推理。
该入口默认 market=hk；也可用 `scripts/us_market.py --market hk`。共享行情适配实现，
模型核心和沪深/北交所脚本保持原样。依赖复用 `scripts/us-requirements.txt`。

## 实际日线查询：Yahoo + 东方财富

用户查询某日实际日线时，使用 `scripts/hk_daily_quote.py`。Yahoo 为价格来源；当 Yahoo 缺少成交额时，从东方财富获取同一证券、同一香港交易日的真实成交额，并获取换手率、核对日线开高低收。仅查实际行情时不调用模型，也不附模型预测提示。

该入口复用 yfinance、exchange_calendars 和 curl_cffi，直接请求东方财富公开港股 K 线接口；也可使用核验过的 AKShare `stock_hk_hist` 接口。Yahoo 证券身份检查包括 HKG、HKD、EQUITY 和香港时区；东方财富代码按五位编号转换，并核对响应市场 116、代码和名称。转码本身不证明历史代码未变更，改名或重用代码需要另行核验。

价格和成交额均标注 HKD，成交量标注股，换手率标注百分数（0.33 表示 0.33%）。Yahoo `auto_adjust=False` 的 OHLC 可能包含拆股调整；东方财富使用 `fqt=0` 不复权。对历史日期核对公司行动、收盘竞价及各源日线范围，价格一致也不证明量额统计范围完全相同。程序只容忍浮点表示误差，保留价格差异和两源成交量，不拼接成宣称同口径的模型 OHLCVA 输入。

传入实际 Python 路径和新输出目录。例如在包根目录，Windows：

```powershell
$py = Join-Path (Get-Location) '.venv-kronos/Scripts/python.exe'
$skill = Join-Path (Get-Location) 'skills/kronos-kline-predict'
& $py "$skill/scripts/hk_daily_quote.py" --symbol 09992 --date 2026-09-28 --output-dir 'outputs/popmart-daily-001'
```

macOS：

```bash
./.venv-kronos/bin/python skills/kronos-kline-predict/scripts/hk_daily_quote.py --symbol 09992 --date 2026-09-28 --output-dir outputs/popmart-daily-001
```

默认使用当前网络代理设置；确认代理链路故障后，可显式加 `--direct` 仅让东方财富请求直连。使用浏览器兼容 HTTP 客户端，网络错误仍直接失败，不自动重试或静默换源，不修改系统代理。下载失败时输出目录可能已包含原始响应和失败阶段记录，再次执行选择新目录。不要将失败或缺字段解释为零成交额。

输出 `daily-quote.csv`、`data-source.json`、`cross-check.json` 和两源原始行情。行情表使用 Yahoo 开高低收，成交额、换手率来自东方财富；展示成交量时明确选用哪一源，保留另一源的差异。`complete_with_price_discrepancy` 表示已取数但价格核验存在差异，展示并调查，不能称为核验通过。接口缺失目标日、证券不符、未收盘、非法 OHLC 或缺成交额会报错。股价乘成交量不是实际成交额。

这项补充面向实际日线查询。预测适配器仍要求 `--price-only`；分钟预测量额没有在本次扩展中接入东方财富。

## 股票身份与数据

- 数据源为 Yahoo Finance / yfinance。支持以港币计价、返回交易所 HKG、类型 EQUITY 的香港股票。
  不自动套用到 ETF、窝轮、牛熊证或人民币/美元柜台。
- 代码可写 `700`、`00700` 或 `0700.HK`，统一为 Yahoo 的 `0700.HK`；阿里巴巴为 `9988.HK`。
  前导零转换不证明上市身份，仍核对证券名称、HKG、HKD、Asia/Hong_Kong 及当前上市状态。
- 日线默认请求2年，1分钟7天，其他分钟周期1个月。`--period` 可显式指定历史请求窗口，
  最终覆盖仍受 Yahoo 周期限制、上市日期和源数据完整性约束，禁止默默缩短 lookback。
- 60/120分钟从30分钟源线按每段交易时段聚合，保留各段最后不足整周期的短K线，标记 partial_bar。
  一个月120分钟数据可能不足400根；明确说明并选取足够的实际历史/合适的用户参数，不补造。
- Yahoo 无真实成交额，因此准备和预测都显式使用 `--price-only`。原始成交量保留用于核验，
  不伪造成交额，不把模型的量额辅助输出当有效预测。
- 复权选项与美股入口一致：`--adjust yahoo` 保留 Yahoo 提供的OHLC，不称其为完全不复权；
  `--adjust auto` 显式启用 Adj Close 比率调整。核验公司行动与历史价格口径。

## 交易时间与数据筛选

XHKG 日历，时区 Asia/Hong_Kong（与北京时间同一UTC+8）。普通日连续交易09:30–12:00、
13:00–16:00；半日市按日历实际收盘处理。普通日1/5/15/30/60/120分钟分别330/66/22/11/6/4根。
半日市5分钟30根。60分钟上午最后一根只有30分钟；120分钟上午最后30分钟、下午最后60分钟。
不跨午休、隔夜或不同交易日聚合。

分钟预测限定连续交易时段：Yahoo午休、夜间、周末的全OHLC为空且成交量为0的非交易占位行，
以及收盘至收盘后10分钟内的竞价/收盘后记录，不进入模型。保留原始 `source.csv`，
逐行排除原因写入 `excluded-source-rows.csv`，数量写入元数据。
正常开市时段内缺失或空K线仍报错，非交易时间有无法解释的真实行情也报错。
不将午休实际成交记录当空行移除；这可能表示证券类型或交易时段选择不符。

日线保留源日线统计口径，可能包含收盘竞价。为避免使用未完成的日线，正常日等到16:10、
半日市等到12:10再视为完整；具体取数仍检查数据源是否到齐。分钟末根收盘不一定等于
日线/收盘竞价价，交叉核验需说明口径，不能直接替换数值。

日历库未必涵盖所有历史临时停市。测试五年日线时发现2023-09-01和2023-09-08
在源数据与日历间存在缺口，程序报错而非补行情。长历史需核对交易所当年的临时停市公告，
不能用普通工作日或一般法定假期替代；指定 `--period` 也不取消所选区间的完整性验证。

## 使用

```powershell
$skill = Join-Path (Get-Location) 'skills/kronos-kline-predict'
$py = Join-Path (Get-Location) '.venv-kronos/Scripts/python.exe'
$prep = 'C:\Users\Lenovo\Documents\Codex\tencent-input-001'
& $py -m pip install -r "$skill\scripts\us-requirements.txt"
& $py "$skill\scripts\hk_market.py" --symbol 0700.HK --interval 5 --lookback 400 --pred-len 66 --price-only --output-dir $prep
& $py "$skill\scripts\predict.py" --csv "$prep\history.csv" --future-csv "$prep\future.csv" --lookback 400 --pred-len 66 --price-only --timezone Asia/Hong_Kong --data-note "$prep\data-source.json" --check-only
```

`pred-len=66` 是未来66根，不自动代表用户指定日期的完整一天；盘中起算或半日市需依据
`schedule.csv` 核对目标范围。日线改 `--interval 1d`，预测根数按用户要求设定。
指定未来某日时须保留历史截止到目标日之间的所有交易K线，超过模型上下文直接说明。

按 data.md 核验最近已收盘行情、保留单源/多源核验状态，检查通过后移除 `--check-only` 并添加
新的预测 `--output-dir`。随后按 schedule.csv 对齐预测CSV，完成 SKILL.md 规定的图表、逐根表格、
中文报告；午休断开，短尾根标注。不要调用沪深专用的 intraday.py summarize。
本次接口验证不代表港股预测准确率或策略收益验证。

交易所交易时间参考：
https://www.hkex.com.hk/Services/Trading/Securities/Overview/Trading-Hours?sc_lang=en
