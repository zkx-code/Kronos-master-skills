---
name: kronos-backtest
description: 按用户提供的 Kronos-master 原项目执行回测与验证：Qlib 滑动窗口推理、TopkDropout 策略与指数基准比较、已有预测 CSV 策略回测，以及原始回归测试。用户要求 Kronos 回测、验证预测、比较策略与基准或复现原项目历史测试时使用。明确区分真实模型回测与原项目随机预测示例；不负责模型训练、实时预测或下单。
---

# Kronos 原项目回测

以用户的 `E:\K线预测\Kronos-master` 为实现依据。`assets/kronos/` 保存该目录回测相关源码的逐字节快照及 MIT 许可证，`source-manifest.json` 记录 SHA256。技能只负责选择入口、传参、工作目录和结果导出；策略、预测与指标公式均调用原代码。

## 操作系统与路径

在完整分发包中首次调用时，先读 [包内环境准备](references/package-environment.md)。由Agent检查并按实际任务准备依赖；用户无需双击任何启动器，已有环境不重复安装。

在 macOS 或迁移到其他电脑时，先读 [平台说明](references/platforms.md)。按当前系统解析 Python、工作目录和模型路径；文档中的 Windows 命令仅为示例。

## 选择原有入口

| 请求 | 入口 | 实际能力 |
| --- | --- | --- |
| 用真实 Kronos 对历史数据滑窗推理、组合策略与指数比较 | `finetune/qlib_test.py` | `QlibTestDataset` → 原始模型推理 → `TopkDropoutStrategy` → Qlib 指标及图 |
| 对已有预测 CSV 运行原项目策略 | `examples/run_backtest_kronos.py` | `KronosBacktester.run_complete_backtest`，买入持有曲线对比 |
| 复现原项目历史示例 | `examples/yuce/historical_backtest.py` | `HistoricalBacktester` 用随机波动生成示例预测；不调用 Kronos |
| 检查官方样例模型输出是否变化 | `tests/test_kronos_regression.py` | 固定 revision 的输出回归及 MSE 测试，不是市场预测准确率证明 |

本快照没有“保持最后价格不变”的比较命令，也没有之前另写的 20 日滚动验证。它们不是原项目功能，此技能不混入这些实现。不替换为 Backtesting.py、Backtrader 或另写撮合引擎。

## 执行流程

1. 先读 [原项目行为与限制](references/source-behavior.md)，按请求选上表入口。真实模型准确性/策略评估优先 Qlib；随机历史示例仅在用户明确要求复现该示例时运行，并称作模拟示例。项目已有替代价格、随机预测和异常吞掉逻辑都在该参考中说明，不能拿来掩盖真实主流程失败。
2. 运行 `scripts/upstream.py stage --work-dir <新任务目录>`，复制原始源码到独立工作目录，保留用户源项目。每次新实验使用新目录；所有命令路径先转绝对路径。`verify` 校验核心源码，唯一允许在工作副本按原项目方式配置的文件是 `finetune/config.py`，配置变化另记 SHA256。
3. Qlib 读取 [Qlib 使用](references/qlib.md)，配置副本的原始 `Config` 类，准备真实 Qlib 数据、test_data.pkl 和匹配权重。CSV/历史示例读取 [CSV 使用](references/csv.md)。数据来源和已知截止时点必须记录；需要获取行情时使用现有 `kronos-kline-predict` 的来源核验流程，不把未来预测当真实成交数据。
4. 执行 `check`，查看依赖、参数和所需文件，修复明确问题后调用 `run`。环境错误、原脚本异常或返回 None 时报告失败，不跳到另一个 profile。用户要求按原项目执行时，不暗改源码中的算法、随机数或成交规则来获得可运行/更漂亮的结果。
5. 核对 `run.json`、`run.log`、原指标和原图，说明具体运行模式、输入来源、基准及局限。源脚本可能把失败捕获后返回 None，封装层会把它转换为非零退出码。只有原函数成功并保存结果才报告完成；仅检查依赖/语法不得写成完成真实回测。

## 调用方式

```powershell
$skill = Join-Path (Get-Location) 'skills/kronos-backtest'
$py = Join-Path (Get-Location) '.venv-kronos/Scripts/python.exe'
$work = 'E:\Kronos-master-skills\outputs\original-backtest-001'
& $py "$skill\scripts\upstream.py" stage --work-dir $work
& $py "$skill\scripts\upstream.py" check --profile qlib --work-dir $work
```

`check` 可以在依赖缺失时运行，不加载模型。`run --profile` 可选 `qlib`、`qlib-preprocess`、`csv-strategy`、`historical-demo`、`regression`；具体参数查看 `--help` 与对应参考。核心包依赖保持原 requirements；Qlib 额外依赖 `pyqlib`，回归测试额外依赖 `pytest`，按使用模式安装，默认不拉取额外行情或启动训练。

## 结果表述

- 区分“预测误差”“策略收益”“程序回归测试”三个不同问题；跑通脚本不代表具备预测优势。
- 原 Qlib 基准是 Config 指定的指数；CSV 示例基准是原价格序列的买入持有。不要称它们为不变价格基线。
- 原历史示例“预测准确率”是相对误差小于 5% 的样本比例，不是方向命中率，其预测源还是随机波动。
- 只报告原代码实际计算过的指标，原输出中的 NaN/无定义值保持无定义，不写成 0。指标时间尺度及费用覆盖按源代码说明，不声称新增滑点、逐笔成交、真实券商约束或样本外保证。
- 若交付真实 Kronos 历史预测/回测结果，在当前对话结尾输出：**本次是依据清华大学开源的模型预测，不是确定的买卖，不要全盘相信，要有自己的判断。** 随机示例则明确说明“本次为原项目随机预测示例，不是 Kronos 模型预测”，不作错误归因。
