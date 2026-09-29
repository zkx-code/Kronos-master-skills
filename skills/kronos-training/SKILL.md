---
name: kronos-training
description: 按用户提供的 Kronos-master 原项目训练流程微调金融 K 线模型：Tokenizer、Predictor、Qlib 数据预处理、CSV 顺序训练、单组件训练和 DDP。用户要求 Kronos 微调、训练专用模型、适配自己的行情或准备 Qlib 训练数据时使用。复用原训练脚本，不负责日常预测、回测或自动下单。
---

# Kronos 训练

复用 `E:\K线预测\Kronos-master` 的原始 `finetune/` 与 `finetune_csv/` 入口。`assets/kronos/` 是带 SHA256 的源码快照；脚本先复制到新的工作目录，再做输入检查，最后从该副本调用原脚本。训练输出、配置和日志写入用户指定的新实验目录，不覆盖原项目或已有 checkpoint。

## 操作系统与路径

在完整分发包中首次调用时，先读 [包内环境准备](references/package-environment.md)。由Agent检查并按实际任务准备依赖；用户无需双击任何启动器，已有环境不重复安装。

在 macOS 或迁移到其他电脑时，先读 [平台说明](references/platforms.md)。按当前系统解析 Python、工作目录和模型路径；文档中的 Windows 命令仅为示例。

## 训练入口

| 任务 | 原项目入口 | 说明 |
| --- | --- | --- |
| Qlib 数据准备 | `finetune/qlib_data_preprocess.py` | 从 Qlib 读取配置时间段和字段，生成 train/val/test pickle |
| Qlib Tokenizer 微调 | `finetune/train_tokenizer.py` | 使用 `finetune/config.py` 和预训练 Tokenizer |
| Qlib Predictor 微调 | `finetune/train_predictor.py` | 使用验证最优 Tokenizer 和 Predictor 配置 |
| CSV 完整顺序训练 | `finetune_csv/train_sequential.py` | 先 Tokenizer，再 Predictor；支持跳过已有阶段 |
| CSV Tokenizer 单独训练 | `finetune_csv/finetune_tokenizer.py` | 只训练量化器 |
| CSV Predictor 单独训练 | `finetune_csv/finetune_base_model.py` | 使用微调后的 Tokenizer 训练 Predictor |
| 多 GPU | CSV 顺序训练 `torchrun` 入口和 Qlib DDP | 保持原 backend、进程数和环境变量；单独 CSV main 不初始化 DDP |

## 固定流程

1. 选择 `qlib` 或 `csv`。CSV 必须是单一标的/周期、严格递增时间，包含 `timestamps,open,high,low,close,volume,amount`；Qlib 必须提供原项目需要的中国市场目录。读取 [数据与配置](references/data.md)，确认历史切分、lookback、predict_window、复权和单位。
2. 执行 `scripts/training.py stage --work-dir <新目录>`，再用 `check` 检查 Python 依赖、数据路径、预训练权重、配置值和输出路径。配置副本只在用户指定的新 work-dir 中修改；原始实现文件哈希不变。
3. 运行 `run` 调用原脚本。默认训练完整 CSV 顺序流程；需要单独阶段时使用 `csv-tokenizer` 或 `csv-predictor`。Qlib 先 `qlib-preprocess`，再 `qlib-tokenizer` 和 `qlib-predictor`。运行日志、实际命令、配置快照和 checkpoint 列表写入 `--output-dir`。
4. 完成后检查 `best_model`、训练日志和验证损失；确认 Tokenizer 与 Predictor 版本匹配，再把 checkpoint 路径交给 `kronos-kline-predict`，最后用 `kronos-backtest` 做滚动验证。训练完成本身不代表泛化效果提高。

## 边界与硬检查

- 不把训练失败改成随机初始化继续训练，不用模拟行情填充空数据，不自动改周期、时间切分、设备或学习率。
- 本地封装要求关闭 use_comet，避免原代码记录/上传含凭证配置。Qlib 原脚本即使关闭 Comet 也直接 import comet_ml，仍需该依赖；外部跟踪另行配置。
- 不在原项目目录直接训练；不覆盖既有模型。输出目录存在时停止，使用新的实验目录。
- Qlib 与 CSV 入口的默认超参数不同，以实际配置副本为准。多 GPU 训练需用户明确配置 `torchrun` 参数；Windows/CPU 不把 `nccl` 静默换成其他 backend。
- 只报告原脚本实际打印或保存的 loss、checkpoint、验证结果。不要把训练 loss 当交易收益或准确率。

## 执行示例

```powershell
$skill = Join-Path (Get-Location) 'skills/kronos-training'
$root = (Get-Location).Path
$py = "$root\.venv-kronos\Scripts\python.exe"
$work = "$root\outputs\training-work-001"
$out = "$root\outputs\training-run-001"

& $py "$skill\scripts\training.py" stage --work-dir $work
& $py "$skill\scripts\training.py" check --profile csv-sequential --work-dir $work --config "$work\finetune_csv\configs\config_ali09988_candle-5min.yaml"
& $py "$skill\scripts\training.py" run --profile csv-sequential --work-dir $work --config "$work\finetune_csv\configs\config_ali09988_candle-5min.yaml" --output-dir $out
```

详细字段、切分和 checkpoint 规则见 [数据与配置](references/data.md)，Qlib 环境见 [Qlib](references/qlib.md)，CSV 命令和 DDP 见 [CSV 训练](references/csv.md)。

`check` 全量检查 CSV 数值、时间顺序、切分样本数、本地权重与设备；交易日缺口、复权口径和标的身份仍需依据来源核验。原 CSV 使用整个样本窗口归一化，包含目标行，不能将验证 loss 宣称为无泄漏的预测准确率。最佳权重不包含恢复训练所需的全部优化器状态，skip-existing 只是跳过阶段。

本 skill 不新增 MAE/RMSE 测试算法；训练与验证 loss 沿用原脚本，实际预测评估交给预测/回测流程。封装验证范围见 [validation.md](references/validation.md)。
