# CSV 训练入口

原项目推荐的完整流程：

```powershell
python finetune_csv/train_sequential.py --config configs/config_ali09988_candle-5min.yaml
python finetune_csv/train_sequential.py --config CONFIG --skip-existing
python finetune_csv/train_sequential.py --config CONFIG --skip-basemodel
python finetune_csv/train_sequential.py --config CONFIG --skip-tokenizer
```

单组件入口：

```powershell
python finetune_csv/finetune_tokenizer.py --config CONFIG
python finetune_csv/finetune_base_model.py --config CONFIG
```

DDP：

```powershell
$env:DIST_BACKEND = 'nccl'
torchrun --standalone --nproc_per_node=GPU_COUNT finetune_csv/train_sequential.py --config CONFIG
```

封装 profile：`csv-sequential`、`csv-tokenizer`、`csv-predictor`。skip 参数只用于 sequential。DDP 也只用 sequential（单组件可通过 skip 选择）；两份单独脚本的 main 不初始化 DDP，并自动选择 CUDA/CPU、忽略 YAML 设备选择，建议优先使用 sequential。DIST_BACKEND 由原代码读取，多进程需实际可用的 CUDA 和 backend；CPU 多进程不会自动改为训练。

YAML 的 `experiment.train_tokenizer/train_basemodel/skip_existing`、`device` 和 `distributed` 由原 `ConfigLoader` 解析；动态路径 `{exp_name}` 在复制后的配置里展开。check 会验证数据 CSV、预训练目录、base_save_path 和已有模型跳过条件，但不会创建虚假 checkpoint。

训练输出通常是：

```text
<resolved_base_save_path>/tokenizer/best_model/
<resolved_base_save_path>/basemodel/best_model/
<resolved_base_save_path>/logs/
```

实际路径以原 YAML 动态解析结果为准，base_path/exp_name 已在其中展开。训练后读取封装输出的 `run.json` checkpoint 列表，配对用于预测并在独立测试段评估。skip-existing 只跳过已有阶段，不恢复优化器、epoch 或学习率调度器；加载已有权重重新训练也不等于完整断点续训。
