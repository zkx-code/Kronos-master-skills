# 原项目行为与边界

以下结论均来自包内原始源码，保留实现不等于认可每种计算都适合实际交易。优先直接查看相应类/函数，调用时报告实际路径。

## 真正的模型滑窗回测：finetune/qlib_test.py

`QlibTestDataset` 枚举每个标的连续窗口，历史 lookback 与未来 predict_window 分开，均值/标准差只按历史计算。模型生成 last/mean/max/min 四种 close 差值信号（标准化空间），再按 datetime/instrument 转成矩阵，交给 Qlib。

默认 Config：lookback=90、predict_window=10、max_context=512、T=0.6、top_p=0.9、sample_count=5；持有 top50、每次替换5、hold_thresh=5，csi300 对应 SH000300；csi800 对应 SH000906，csi1000 对应 SH000852。它不是先前 skill 的 lookback400/单次采样设置。

`QlibBacktest.run_single_backtest` 原样硬编码：初始账户 100,000,000；daily；开盘成交；limit_threshold=0.095；open_cost=0.001、close_cost=0.0015、min_cost=5；SimulatorExecutor 配有 delay_execution=True。原函数没有独立滑点参数，不扩大“有费用”到“模拟所有交易摩擦”。其图中的累计收益使用 `cumsum()`，并非自行改成复利 `cumprod()`。

报告基准收益、扣/不扣费用的超额收益，图含策略及指数。`generate_predictions()` 内部重新创建 `Config()`；只改外围字典可能不改变数据窗口，需按原项目修改同一工作副本的 Config。DataLoader 的 num_workers=os.cpu_count()//2，Windows 下多进程和当前 Qlib 接口版本需实际验证。没有真实 Qlib 数据和权重时，完成条件只到环境/参数检查。

## 已有预测 CSV 策略：examples/run_backtest_kronos.py

`KronosBacktester` 加载实际 close 与已有 predicted_close。先优选历史结束之后的预测；如果没有，原 `align_data` 会使用所有预测。信号来自**预测价格自身的 pct_change**，默认阈值 ±2%；0 信号 forward-fill。不是以每个预测起点的最后真实价格生成可审计的无泄漏信号。

原 `run_backtest` 在没有实际价格时使用预测价格充当成交/估值价格，原图的买入持有基准也使用该混合价格序列。因此必须说明是真实历史价格回放还是预测价格情景模拟，不能把后者当真实回测收益。封装不增添自己的价格兜底，也不改变这些分支。

原持仓及资金逻辑简化，正负信号都可能用于开仓，反向信号不等同于健全的平仓再开仓规则。没有手续费、滑点、A 股 T+1、整手或涨跌停队列模拟。年化按252和每行一日计算，所以传入分钟数据的年化指标不具备日频含义。风险自由收益率固定3%。不要为获得“合理”指标而静默修正原代码。

`run_complete_backtest` 只保存 PNG 并返回 metrics/results/trades；封装额外把这三个原返回值序列化成 JSON/CSV，未增加指标公式。`main()` 中 D 盘路径、000831 是示例配置，封装直接传构造函数/方法的同名参数，不执行该硬编码 main。

## 随机历史示例：examples/yuce/historical_backtest.py

类名 `HistoricalBacktester` 容易误导。`simulate_model_prediction` 每 pred_days 行取一个起点，默认 lookback_days=60、pred_days=30；真正调用的是 `simple_prediction`，其价格按 `np.random.normal(0, 历史收益标准差)` 逐步扰动。没有加载 Tokenizer 或 Kronos，源码未固定随机种子。技能不偷偷把它替换为模型，也不为其成绩背书。

`calculate_prediction_accuracy`：平均绝对误差率、误差小于5%的比例、`diff()` 方向一致率、相关系数。方向计算会跨窗口边界。交易策略以同一行 actual_close 同时计算预测收益和成交，未模拟信号可用时间/下一根成交；默认阈值3%，满仓买卖。原代码未把 results_df 的 date 列设成索引，后续记录可能保留整数 date，并在有交易时 `.strftime()` 报错；遇到该错误如实报告，不把原实现缺陷掩盖掉。

## 模型回归测试：tests/test_kronos_regression.py

原 pytest 覆盖 context=512/256、8步输出与保存快照比较，以及4个抽样窗口的30步 MSE。CPU，seed123，top_k1，top_p1；模型 revision 901c26c1332695a2a8f243eb2f37243a37bea320，Tokenizer revision 0e0117387f39004a9016484a186a908917e22426。测试会从对应 Hub revision 取权重，需准备缓存/网络。它检验实现回归，不证明某只股票能赚钱；不要重新生成 expected CSV 后宣称原测试通过。

## 本次封装验证范围

原文件 SHA256 与用户项目一致。可执行封装验证见 [validation.md](validation.md)；若某原路径只通过静态/依赖检查，应明确说出，不声称全套实际回测已经跑通。
