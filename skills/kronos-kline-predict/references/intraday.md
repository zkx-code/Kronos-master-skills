# 盘中 1 / 5 / 15 / 30 / 60 / 120 分钟预测

用户问“某天几点涨跌、盘中走势、上午下午走势”时走此分支，默认 5 分钟；其他指定周期优先。模型复用原始 Kronos，输入必须来自同周期的真实分钟行情，日线预测不得拆分插值成分钟预测。

## 范围与交易时间

`scripts/intraday.py` 支持 `--market cn`（默认，沪深 A 股）和 `--market bse`（北交所）。常规交易时段为09:30–11:30、13:00–15:00，使用 exchange_calendars 的 XSHG 会话，时间为 Asia/Shanghai，K 线采用收盘标签。北交所将 XSHG 作为共用会话代理，须按 [data.md](data.md#北交所股票) 核验北交所休市与停牌，元数据明确记录此限制。全天 1/5/15/30/60/120 分钟分别 240/48/16/8/4/2 根；60分钟对应09:30–10:30、10:30–11:30、13:00–14:00、14:00–15:00，120分钟对应09:30–11:30、13:00–15:00，午休不合并。收盘集合竞价属于数据源实际对应的 K 线，开盘竞价按行情源原始聚合规则保留；不自行重建集合竞价。

目标日休市直接报告该日无交易，不自动换成邻近交易日。准备脚本排除 as-of 之后未收盘的 bar；预测历史日期时固定在目标日开盘前截断，目标日价格另存真值。历史窗口内漏 bar、时间标签/周期错误或最新 bar 落后于 as-of 对应已结束 bar 都报错，不填充或静默缩短窗口。停牌标的需要单独说明数据条件。

目标日不紧邻输入截止日时，脚本生成所有中间交易日的分钟 bar，最后提取目标日；horizon 超出模型上下文则报错。本脚本只做整个目标交易日的开盘前预测，盘中“从当前时刻预测余下时段”需要单独按当前 cutoff 准备输入和未来时间，不把当天已知价格混入开盘前预测。

## 数据来源

先按 [data.md](data.md) 核验权威来源和标的，再选择 `--source sina`、`eastmoney` 或 `csv`，不在脚本中自动换源。沪深支持上述三种来源；北交所自动取数使用东方财富，或显式读取已核验 CSV，拒绝新浪路径。官方交易所日历、证券名录优先；实际分钟行情可能来自金融数据商，必须注明真实提供方。

- 新浪使用 AKShare `stock_zh_a_minute(symbol='sh600519', period='5', adjust='')`，通常返回约 1970 根。当前接口包含真实 amount 时可保留，缺 amount 时直接报错或明确采用 price-only，禁止估算成交额。
- **新浪自动取数仅支持不复权**。当前 AKShare 在复权失败时可能返回原始价格，并可能因日线归档滞后丢掉当天分钟数据；因此本脚本拒绝新浪 qfq/hfq。需要复权时选择核验过口径的 CSV 或东方财富接口，记录复权依据。不复权历史跨除权日需要在运行前识别、说明影响或使用可靠复权数据。
- CSV 使用 `--time-column day` 等适配实际列名。脚本保存输入 SHA256 和来源说明，但不证明用户声明的标的、单位或复权正确。
- 将最近完整交易日分钟 OHLC 聚合为 open=first/high=max/low=min/close=last，volume/amount 求和，与可信的同口径日线/收盘后快照核验。跨来源价格以最小报价单位检查，成交量/额差异查清计量单位及竞价覆盖。保存核验文件，不通过则停止后续推理。

## 北交所

使用 `--market bse`，`--symbol` 传入已核验的六位北交所代码或 `bj` 前缀代码。东方财富取数前会移除 `bj`；沪深仍使用 `sh`/`sz` 前缀，不因这次扩展改变原有命令。

以下示例中的 `$bseCode`、`$targetDate`、`$dataNote` 应来自本次身份、日期和口径核验；`$skill`、`$py`、`$prep` 为实际路径，`$prep` 必须是新目录。

```powershell
& $py "$skill\scripts\intraday.py" prepare --market bse --source eastmoney --symbol $bseCode --minutes 5 --target-date $targetDate --adjust none --data-note $dataNote --output-dir $prep
```

已有核验后的本地分钟行情时，可显式选择 CSV：

```powershell
& $py "$skill\scripts\intraday.py" prepare --market bse --source csv --csv $verifiedCsv --symbol $bseCode --minutes 5 --target-date $targetDate --adjust none --data-note $dataNote --output-dir $prep
```

取数失败保留源错误，不自动改用 CSV 或其他来源。东方财富不同分钟周期的实际覆盖要逐次核验；一分钟不支持复权。准备成功后沿用下文 `predict.py --check-only`、正式推理、`summarize` 流程，预测根数读取 `data-source.json` 的 `prediction_length`。`market=bse` 和 `exchange=BSE` 写入数据来源记录。增加市场接入不代表已证明北交所预测准确率。

## 执行

### 1 分钟模式

在下方 prepare 命令使用 `--minutes 1`，随后从 data-source.json 读取实际 prediction_length 传给 predict，不沿用 5 分钟的48根。完整单日包含09:31–11:30和13:01–15:00两个区段，每段120根；09:30和13:00为区段起点，不额外生成收盘标签。`--lookback 400` 是400根分钟线，不是400天。

自动取数把 `period='1'` 传给成熟的 AKShare 接口，或读入已核验的一分钟 CSV。东方财富该周期调用 trends2/get（当前 AKShare 请求最近5天），并不应用 adjust 参数；脚本拒绝该源一分钟 qfq/hfq，避免误标复权。部分来源可能有09:30快照、零值open、或收盘集合竞价阶段缺分钟：必须核对来源定义；校验失败直接报告，不补值、不悄悄删行、不复制上一分钟凑240根。需要转换标签时另存并记录转换依据。

本模式继承未收盘排除、时间缺口与历史/目标隔离检查。small/base 的未来步数限制仍为512；一天240根可调度，跨三天720根会报超限，不跳过中间交易日。原 README 示例为5分钟；本扩展利用通用时间戳接口，不代表原项目已声明一分钟效果。发布一分钟结果时说明尚未完成该周期准确率验证；本次实现验证覆盖时间调度与命令流程，尚未实测一分钟行情服务或真实模型推理。

### 60 分钟模式

使用 `--minutes 60`。A股单日目标长度为4根，上午和下午各2根；60分钟是交易时段内的闭区间聚合，不把午休拼进一根K线。自动行情接口用 `period='60'`；新浪/东方财富返回的标签和是否包含开盘集合竞价必须按实际响应核对。该周期目前只完成调度、输入检查和命令流程测试，尚未完成多日准确率验证；不要把60分钟结果与30分钟结果混算。

### 120 分钟模式

使用 `--minutes 120`。A股单日目标长度为2根：09:30–11:30、13:00–15:00，午休严格分隔。自动行情接口使用 `period='120'`；实际数据源可能把标签记为区间起点或终点，必须以源字段和聚合验证结果为准。该周期目前只完成调度、输入检查和命令流程测试，尚未完成多日准确率验证。

依赖沿用核心 requirements，另需 `akshare`、`exchange_calendars`（见 `intraday-requirements.txt`）。已安装依赖和权重时复用，不重复安装。

PowerShell 示例（路径按实际技能/任务目录替换）：

```powershell
$skill = Join-Path (Get-Location) 'skills/kronos-kline-predict'
$root = (Get-Location).Path
$py = "$root\.venv-kronos\Scripts\python.exe"
$prep = "$root\outputs\intraday-input-001"
$out = "$root\outputs\intraday-forecast-001"
& $py "$skill\scripts\intraday.py" prepare --source sina --symbol sh600519 --minutes 5 --target-date 2026-09-22 --adjust none --data-note '贵州茅台；新浪；价格元、成交量股、成交额元；已完成日线聚合核验，详见任务核验文件' --output-dir $prep
$meta = Get-Content "$prep\data-source.json" -Raw | ConvertFrom-Json
& $py "$skill\scripts\predict.py" --csv "$prep\history.csv" --future-csv "$prep\future.csv" --lookback 400 --pred-len $meta.prediction_length --model small --timezone Asia/Shanghai --model-path "$root\models\Kronos-small" --tokenizer-path "$root\models\Kronos-Tokenizer-base" --check-only
```

核验完成、检查通过后，同一预测命令去掉 `--check-only`，添加 `--output-dir $out` 和 `--data-note "$prep\data-source.json"`。保留原参数和指定设备；prepare 若用了 price-only，predict 必须同样显式传入。然后：

```powershell
& $py "$skill\scripts\intraday.py" summarize --prepared-dir $prep --forecast-dir $out
```

输出 `intraday.csv`、`盘中预测.md`：每根实际时间区间、OHLCVA、相邻收盘涨跌、根内开收涨跌、合法性标记。历史截至哪个时点、目标日期和 period 必须一致；summary 通过 SHA256 验证它与真正预测输入的绑定。

## 解读“什么时候涨跌”

报告为“模型路径预计 09:35–09:40 收盘相对上一根偏强”等。`close_change_pct` 是该根收盘相对上一根收盘（第一根对最后真实收盘），`candle_change_pct` 是该根开盘到收盘变化。开盘、午休边界单独标记，不把隔夜/午休跳空归为连续交易涨幅。

涨跌时段是分钟粒度的估计；一根收涨的 K 线内部仍可能先跌后涨。最高/最低只能定位到该根覆盖的区间，不能给区间内精确秒数。多次采样平均也不自动产生上涨概率；未做独立留出验证时不声称准确率。日线与分钟线分别运行，结果可能不同，不能把之前日线目标价格强行套进分时路径。

异常 OHLC 原值保留、图上标记，summary 不把异常高低价用于宣布有效极值时段。图优先展示带实际时刻、午休断开的预测收盘路径，必要时另加合法的 K 线图；不要连成午休期间仍有连续成交的假象。
