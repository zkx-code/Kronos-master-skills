# 原WebUI实际行为

来源：用户Kronos-master快照，source-manifest.json记录10个原文件哈希，保留MIT许可证。不要只按上游README概括，以下已核对app.py和templates/index.html。

- 前端lookback=400、pred_len=120是readonly。滑块以时间跨度选择窗口，实际推理按所选start_date后首400行，再取后120行时间作为目标及真实对照。
- 不传start_date时，原代码虽然称“latest data”，实际上取文件**最前面**400行输入与随后120行时间；结果表却可能把标签从文件末端向后生成。使用时明确选择start_date并核对实际切片。
- 图及结果表用文件最初两个时间点间距构造date_range，跨午休、夜盘、周末或节假日会出现标签偏移。真实模型使用的目标时间与展示标签可能不同。这是原实现局限，不是交易日历已校准的预测图。
- 原loader缺时间列时生成自2024-01-01开始的小时序列；数值转换失败或其他列缺失会dropna。封装导入和请求检查阻止这些输入，要求用户另存真实、完整数据。
- 原UI只将OHLC及可选volume传给Kronos，**排除真实amount**；有volume时上游Predictor会估算amount，无volume时补零。它与现有CLI的完整OHLCVA或显式price-only模式不同，不能直接把结果差异解释为模型准确率变化。
- 原run.py和app.py有“模拟数据”提示文字，但实际 `/api/predict` 在没加载真实模型时返回400，不生成可用预测。封装在启动时先检查真实模型导入，失败立即退出。
- 原load-model没有显式eval调用、seed接口或完整参数验证；不要声称与CLI固定seed的输出逐位一致。预训练权重在CPU/GPU切换后可能不同。
- 图表用Plotly.js CDN，HTTP请求用axios CDN，浏览器需能访问；服务HTTP200不等于CDN和图表加载成功。
- 原app存在全局单一模型状态、任意文件路径API及CORS，适合个人本地任务。封装只监听loopback、关闭debug，文件请求限制为工作副本data目录，默认单线程；不把此启动器描述成生产多用户服务。

本skill不改原推理或图表算法。需要准确交易时间或盘中实时更新时用kronos-kline-predict；需要修复原WebUI时另立明确修改任务，记录差异后再声称原图表已校正。

用户后来明确要求中英文界面，新增 `scripts/localization.py` 展示层翻译：静态标签、动态提示、对比表与图例/坐标标题翻译；原文件继续通过快照哈希核对。API数值、时间戳、字段名、文件名和持久化结果保持原语义。底层异常的技术细节可能保留原文，以便定位错误。语言切换刷新前端，不会触发重新预测或清空已保存文件。
