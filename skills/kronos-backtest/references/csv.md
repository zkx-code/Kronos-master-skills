# 原 CSV 入口

先 stage，以下 `$work` 是新生成的工作副本，`$out` 必须是新输出目录。

## csv-strategy：使用已有真实预测文件

原脚本要求历史文件位于 `data_dir/<stock_code>_stock_data.csv`，预测文件按顺序寻找：`<stock_code>_kronos_predictions.csv`、`<stock_code>_detailed_predictions.csv`、`<stock_code>_predictions.csv`。为避免选错，指定目录只放本次要用的一份预测。

历史至少需要 date、close；绘图/来源检查建议保留 OHLCVA。原映射支持 日期、开盘价、最高价、最低价、收盘价、成交量、成交额。预测至少需要 date、predicted_close；支持 日期、预测收盘价、收盘价等原映射。现有 predict skill 的 timestamps/close 不符合此文件约定，可另存一份仅做列名适配的副本，并记录转换；不能把实际行情改名后冒充历史预测。

```powershell
& $py "$skill\scripts\upstream.py" run --profile csv-strategy --work-dir $work --stock-code 600519 --data-dir 'E:\行情\历史' --prediction-dir 'E:\行情\当时保存的预测' --output-dir 'E:\Kronos-master-skills\outputs\csv-original-001' --initial-capital 100000 --threshold 0.02
```

该命令直接调用原 `run_complete_backtest`，默认参数完全来自原方法。输出额外序列化为 metrics.json、equity.csv、trades.json，图仍是原 `plot_backtest_results`。先核对 [source-behavior.md](source-behavior.md) 的预测价格成交、缺少费用、时间对齐等限制。

## historical-demo：复现原随机示例

仅在用户明确要求复现时选择。它使用历史 CSV，但“预测”来自随机波动，名称里的 Historical 不代表真实 Kronos 滚动验证。

```powershell
& $py "$skill\scripts\upstream.py" run --profile historical-demo --work-dir $work --stock-code 600519 --data-dir 'E:\行情\历史' --output-dir 'E:\Kronos-master-skills\outputs\random-original-001' --initial-capital 100000 --lookback-days 60 --pred-days 30 --threshold 0.03
```

不新增随机种子参数，保留原脚本随机行为。返回 accuracy/performance/results 按原值保存；原代码出错则退出并保存日志，不换成真实模型或另一回测方案。其误差5%以内占比不能包装为涨跌命中率。
