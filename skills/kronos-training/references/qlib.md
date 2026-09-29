# Qlib 入口

原项目入口顺序：

```powershell
python finetune/qlib_data_preprocess.py
torchrun --standalone --nproc_per_node=NUM_GPUS finetune/train_tokenizer.py
torchrun --standalone --nproc_per_node=NUM_GPUS finetune/train_predictor.py
```

封装只调用这些原文件。默认 launcher=auto 在 Qlib 训练时使用 `python -m torch.distributed.run --standalone --nproc_per_node=1`，单GPU也需DDP；预处理用普通Python。多GPU可用 `--launcher torchrun --nproc-per-node N`。

原 setup_ddp 固定 CUDA/NCCL，Windows 原生环境不支持该路径，需在兼容的 Linux/WSL CUDA 环境执行。封装会报告平台限制，不改 backend。comet_ml 是两份训练脚本无条件导入的包，即使关闭跟踪也需安装。

训练前需要：

- `pyqlib` 与原 requirements 兼容；
- Qlib CN 数据目录；
- 预训练 Tokenizer/Predictor checkpoint；
- 可写的新 dataset、model 和结果路径；
- 与 device/backend 匹配的 PyTorch。

原 Config 的 `train_time_range`、`val_time_range`、`test_time_range` 和 `backtest_time_range` 是独立字段，封装不会把它们自动改成不重叠。预处理结束后必须检查 pickle 的键、字段和日期范围，再开始训练。

Qlib 训练脚本中的 checkpoint 命名、验证选择和日志由原实现决定。skill 只在结束时检查预期目录是否存在并记录文件清单；缺失就报告失败。
