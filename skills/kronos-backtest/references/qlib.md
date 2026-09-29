# 原 Qlib 与回归测试入口

## 配置工作副本

stage 后编辑 `$work/finetune/config.py` 的原 Config。建议配置**绝对路径**，因为启动 cwd 为 `$work/finetune`：

- qlib_data_path：真实 Qlib 中国市场目录，含 calendars、instruments、features。
- dataset_path：包含可信来源 test_data.pkl 的目录。结构为 symbol→DataFrame，datetime 索引，特征列 open/high/low/close/vol/amt，与原预处理器一致。
- finetuned_tokenizer_path、finetuned_predictor_path：匹配的真实权重目录；原属性由 save_path 等构造，也可按原代码编辑成绝对路径。原主程序不读取 pretrained_* 来替代这两个路径。
- backtest_result_path、backtest_save_folder_name：本次结果位置。
- instrument、数据时间切分、backtest_time_range、窗口和采样参数：修改时先核对数据区间和测试段隔离，修改 instrument 同时通过 `_set_benchmark` 对应到指数。

stage 的副本里原核心代码保持一致，`verify` 允许 Config 内容按用户参数变化并记录新旧哈希。Config 是 Python 文件，不支持原项目不存在的 JSON 配置覆盖。

## 环境

使用 Python 3.10–3.12，优先复用匹配版本的既有环境：

```powershell
& $py -m pip install -r "$work\requirements.txt"
& $py -m pip install pyqlib
```

只有选 regression 才需 pytest。这里的 Qlib 包名是 pyqlib，导入名是 qlib。先核对当前 Qlib 版本是否接受原 SimulatorExecutor 的参数和 TopkDropoutStrategy；不为兼容而静默改源码。原项目依赖文件没有固定 pyqlib 版本，检查可导入不代表端到端兼容。

## 原流水线

```powershell
# 尚未生成数据时才调用原预处理器
& $py "$skill\scripts\upstream.py" run --profile qlib-preprocess --work-dir $work --output-dir 'E:\Kronos-master-skills\outputs\qlib-preprocess-001'
# 已有数据与模型后执行真实推理和策略回测
& $py "$skill\scripts\upstream.py" run --profile qlib --work-dir $work --device cuda:0 --output-dir 'E:\Kronos-master-skills\outputs\qlib-run-001'
```

启动器使用原脚本 main，不重写 QlibDataset、信号、策略或指标。原 `predictions.pkl` 保存到 Config 指定位置，原图固定为 `$work/figures/backtest_result_example.png`；启动器的 output-dir 只放执行记录和日志。不要把这两个输出位置混淆，也不要以日志存在判断原策略成功。

## 原始回归测试

```powershell
& $py "$skill\scripts\upstream.py" run --profile regression --work-dir $work --output-dir 'E:\Kronos-master-skills\outputs\regression-001'
```

工作目录为原项目根，执行 `python -m pytest tests/test_kronos_regression.py -q`。原模型和 Tokenizer 的 Hub ID/revision 保留；已有权重在其他 local_dir 不等于已有 Hub 缓存。准备缓存时固定相同 revision。不要改 fixture、期望误差或模型路径来凑“通过”。
