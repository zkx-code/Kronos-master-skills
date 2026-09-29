# 上游接口与来源

本技能提取自用户提供的 `E:\K线预测\Kronos-master`。上游地址：<https://github.com/shiyu-coder/Kronos>。打包保留模型核心 3 个 Python 文件、requirements.txt 与 MIT LICENSE；`assets/kronos/source-manifest.json` 记录本次来源及 SHA256。模型文件逐字节复制，不含训练数据、Web UI、本地扩展例子或模型权重。

## 模型对应关系

| 模型 | Tokenizer | 最大上下文 |
| --- | --- | --- |
| NeoQuasar/Kronos-mini | NeoQuasar/Kronos-Tokenizer-2k | 2048 |
| NeoQuasar/Kronos-small | NeoQuasar/Kronos-Tokenizer-base | 512 |
| NeoQuasar/Kronos-base | NeoQuasar/Kronos-Tokenizer-base | 512 |

这些映射来自该快照 README。large 在该快照中未开放，不列为可执行选项。上下文超限在封装层报错，避免上游静默截断造成与用户参数不一致。

## 核心 API

`from model import Kronos, KronosTokenizer, KronosPredictor`

先把包内 `assets/kronos` 加入 import 搜索路径。`KronosPredictor(model, tokenizer, device=..., max_context=...)`；`predict(df, x_timestamp, y_timestamp, pred_len, T=1.0, top_k=0, top_p=0.9, sample_count=1, verbose=True)` 返回以未来时间为索引的 open/high/low/close/volume/amount DataFrame。时间输入使用重置索引后的 pandas Series，因为内部访问 `.dt`。

`predict_batch(df_list, x_timestamp_list, y_timestamp_list, pred_len, ...)` 可复用 GPU 并行推理，按输入顺序返回结果；每个历史窗口等长，未来根数一致。调用前保持单序列相同的数据/时间校验。包内 CLI 每次处理一个标的。

上游缺 volume 时把 volume/amount 置零，只有 volume 缺 amount 时用平均 OHLC × volume 估算。本封装默认要求两列齐全；显式 `--price-only` 才使用零成交量语义。单次 predict 在生成结束会平均 sample_count 条采样路径，未直接暴露路径分布。

## 原项目扩展

原目录 `examples/prediction_new.py` 含请求失败生成模拟行情的逻辑；`prediction_cn_markets_day.py` 使用 bdate_range 并修正/裁剪价格。这些不是本 skill 的预测入口。`examples/run_backtest_kronos.py` 的时间对齐分支也不能直接当作无泄漏的回测保证。

需要微调时才回到用户原项目：`finetune/` 是 Qlib 路径，`finetune_csv/` 是 CSV 扩展。先核对各自配置、数据切分、训练设备和实际调用入口；避免在预测请求中自动启动训练。原项目移动后需提供新路径或从上游获取训练源码。
