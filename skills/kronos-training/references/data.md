# 数据与配置

## CSV

原 `finetune_csv` 要求以下列：`timestamps,open,high,low,close,volume,amount`。每个文件只放一个标的和一个周期。时间转为 pandas datetime，严格递增且唯一；价格有限且大于零，high 覆盖 open/close/low，low 不高于 open/close/high，成交量和成交额非负。缺失字段、时间缺口、重复时间或 OHLC 关系异常停止训练，不插值、不生成替代行情。没有量额时只有在配置明确承认的情况下填零，并在实验记录中标注。

原 CSV 样本窗口为 `lookback_window + predict_window + 1`，train 和 val 切分各自必须严格大于此长度，train 还须构成一个完整 batch（drop_last=True）。`train_ratio/val_ratio/test_ratio` 按行序切分，比例总和为1；默认示例 test_ratio=0，没有独立测试集。

原 CSV 用整个样本窗口计算归一化统计量，包含随后作为预测目标的行。验证 loss 不等于严格历史归一化下的样本外效果，保留原逻辑并披露这一限制。

封装要求 `model_paths.pretrained_tokenizer` 和 `pretrained_predictor` 是匹配的本地目录，含 config.json 及真实权重文件；Hub 权重提前下载到本地。Tokenizer 先于 Predictor；`finetuned_tokenizer` 指向本次 Tokenizer 的 best_model。`base_save_path` 由原 ConfigLoader 展开，最终在该目录内创建 tokenizer/best_model 和 basemodel/best_model，不再额外拼接一次 exp_name。

## Qlib

原 `finetune/qlib_data_preprocess.py` 通过 `Config.qlib_data_path` 初始化 Qlib，读取 `instrument`、`dataset_begin_time` 到 `dataset_end_time`，字段为 open/close/high/low/volume/vwap，并根据 lookback 和 predict_window 扩展边界。它将数据保存到 `dataset_path` 下的 `train_data.pkl`、`val_data.pkl`、`test_data.pkl`。

原 `finetune/dataset.py` 加载 train/val pickle，使用 Config 的时间特征和随机窗口采样；`train_predictor.py`、`train_tokenizer.py` 读取同一 Config。配置中的 train/val/test 时间段存在 lookback 重叠是原项目设计，封装不擅自改切分；报告实际时间范围。

Qlib 需要本地中国市场数据目录和 `pyqlib`。先运行 check，确认 `qlib.init` 能读取 calendar/instruments/features，再运行预处理。没有数据或数据字段不匹配时停止。

## Comet 与凭证

原 Qlib Config 默认 use_comet=True 且有占位配置；本地封装要求在配置副本中显式关闭，避免原代码上传完整配置。Qlib 原文件仍无条件 import comet_ml，关闭跟踪不免除安装依赖。CSV 默认关闭。外部跟踪需用户另行明确要求后单独配置，不通过本封装静默启用。

## 训练后检查

至少核对：Tokenizer `best_model`、Predictor `best_model`、配置快照、训练日志、验证损失、实际 git/source manifest。将这两个目录作为一对交给预测 skill；单独替换其中一个会改变 Tokenizer/Predictor 兼容关系。用留出或滚动数据在 `kronos-backtest` 验证，不用训练集 loss 推断未来收益。
