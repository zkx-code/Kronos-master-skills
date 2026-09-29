# 验证范围

本次使用原WebUI源码及模板、已有Kronos-small与Tokenizer-base本地权重验证，推理设备为RTX4060 CUDA。没有改写原HTML、Flask预测接口、图表算法或模型源码。

已完成：

- 10个原文件与用户 `E:\K线预测\Kronos-master` 字节/哈希核对；独立stage、导入660行已有日线文件、依赖检查。
- Playwright真实浏览器加载原页面及CDN；数据选择与加载、模型选择、CUDA权重加载正常。
- 原 `/api/predict` 完成400输入＋120目标的历史窗口推理；原 Start Prediction 按钮实测成功；Plotly SVG可见、比较表120行、无pageerror。
- 原程序在工作副本 webui/prediction_results 生成JSON结果。它们属于界面/接口验证，不是新发布的市场预测，也不证明准确率。
- 缺少文件路径和工作data目录之外的请求被封装层拦截；不会在这些情况下走原loader的自动造时间或删空行分支。
- 测试页面刷新后需再次点击Load Model的行为已记录。

当前截图和测试记录位于创建工作区 `outputs/kronos-webui-validation/`，不随skill打包用户行情和测试预测。mini/base、CPU/MPS、Feather路径未在本次端到端测试。

已知限制仍保留：400+120固定窗口；展示时间可能跨交易休市而偏移；amount不输入模型；原加载未显式固定seed/eval。这些在behavior.md中说明，不能以“页面测试通过”宣称全部模型行为正确。

## 中英文展示扩展

后续按用户要求添加中英文翻译层。Playwright实际验证中文初始页面、数据加载提示、CUDA模型加载、预测按钮、中文图例/坐标与120行比较表，以及中文→英文→中文切换。两种页面均无JavaScript pageerror；中文脚本另通过Node语法检查。

同一保存结果分别经过英文原响应和中文翻译处理，prediction_results、actual_data及图表OHLC/时间数组一致。语言CLI参数为必填，新一次启动先在对话中询问；明确指定语言则直接采用。原快照哈希仍保持一致，中文视图由scripts/localization.py生成。
