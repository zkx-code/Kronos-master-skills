# 环境与运行示例

下面 PowerShell 示例的 `$skillRoot` 改为实际技能安装目录，`$runRoot` 为用户任务目录。路径包含中文/空格时保留引号。默认使用自动发现的标准技能目录安装位置。

```powershell
$skillRoot = Join-Path (Get-Location) 'skills/kronos-kline-predict'
$runRoot = (Get-Location).Path
python -m venv "$runRoot\.venv-kronos"
& "$runRoot\.venv-kronos\Scripts\python.exe" -m pip install -r "$skillRoot\assets\kronos\requirements.txt"
```

推荐独立 Python 3.10–3.12 环境以适配原项目固定版本；先检查现有 Python 和依赖，不重复创建已有环境。CUDA 用户按 PyTorch 官方安装说明选择与驱动匹配的构建，随后安装其他依赖。所有模型来自 `Kronos*.from_pretrained`，首次联网下载权重，后续复用 Hugging Face 缓存。不要把大权重或虚拟环境放入技能包。

## 交易时段市场预测

```powershell
& "$runRoot\.venv-kronos\Scripts\python.exe" "$skillRoot\scripts\predict.py" --csv "$runRoot\history.csv" --future-csv "$runRoot\future.csv" --lookback 400 --pred-len 20 --model small --timezone Asia/Shanghai --data-note '指定股票代码；日线；数据源与复权参数；volume及amount单位' --check-only
```

检查通过后去掉 `--check-only` 并添加 `--output-dir "$runRoot\outputs\forecast-001"`。每次使用新目录，保留已有运行结果。`--check-only` 只依赖 numpy/pandas，不加载 torch，不下载权重，不产生预测。

## 连续市场

```powershell
python "$skillRoot\scripts\predict.py" --csv "$runRoot\btc.csv" --continuous-freq 1h --price-only --lookback 400 --pred-len 24 --timezone UTC --output-dir "$runRoot\outputs\btc-001"
```

这里显式选择纯 OHLC 模式，脚本忽略输入的 volume/amount 并在元数据中记录零成交量输入。要利用真实成交量时移除该参数，并提供完整 OHLCVA。

## 历史留出验证

```powershell
python "$skillRoot\scripts\predict.py" --csv "$runRoot\history.csv" --holdout --lookback 400 --pred-len 20 --output-dir "$runRoot\outputs\evaluation-001"
```

最后 20 行作为真实结果，之前最近 400 行作为模型上下文。完整输入至少 420 行；不会把留出价格输入模型。报告预测 close MAE/RMSE、最后已知收盘价基线的 MAE/RMSE 和两者相对比较。这是单次留出评估，不是滚动策略回测。

## 模型与采样

| 参数 | 默认 | 约束/含义 |
| --- | --- | --- |
| `--model` | small | mini / small / base |
| `--lookback` | 400 | mini 上限 2048；small/base 上限 512，至少 2 |
| `--pred-len` | 20 | 正整数，不超过所选模型 context；更长预测需另行评估 |
| `--device` | auto | 初始依次选择 CUDA、MPS、CPU；显式设备不可用时直接报错 |
| `--sample-count` | 1 | 正整数；平均路径数量，越大资源开销越高 |
| `--temperature` / `--top-p` | 1.0 / 0.9 | 正温度，0 < top-p ≤ 1 |
| `--seed` | 42 | 记录 Python/NumPy/PyTorch 随机种子；跨设备/版本不承诺逐位相同 |
| `--model-path` / `--tokenizer-path` | 模型对应 Hub ID | 本地权重目录或兼容 Hub ID，须成对提供并匹配 `--model` 架构 |
| `--model-revision` / `--tokenizer-revision` | Hub 默认 | 用提交 hash 固定远程权重版本，复现实验时指定 |

`forecast.csv` 保留六个模型输出列，时间索引为 timestamps。`run.json` 保存输入文件 SHA256、采样参数、来源说明、上下文、设备和库版本，原始 OHLC/成交量质量计数，以及验证误差。异常路径不会写成成功状态。
