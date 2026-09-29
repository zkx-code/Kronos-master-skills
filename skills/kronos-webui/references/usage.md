# 启动、使用和停止

PowerShell示例，路径按本机修改：

```powershell
$skill = Join-Path (Get-Location) 'skills/kronos-webui'
$root = (Get-Location).Path
$py = "$root\.venv-kronos\Scripts\python.exe"
$work = "$root\outputs\webui-session-001"
& $py "$skill\scripts\webui.py" stage --work-dir $work
& $py "$skill\scripts\webui.py" add-data --work-dir $work --file "$root\outputs\maotai-20260921\history.csv"
& $py "$skill\scripts\webui.py" check --work-dir $work
& $py "$skill\scripts\webui.py" serve --work-dir $work --port 7070 --cache-dir "$root\.cache" --language zh
```

每次启动先询问中文还是英文（本次明确指定过则直接采用），不要默认沿用上一次的答案。中文命令传 `--language zh`，英文传 `--language en`，缺少语言参数会报错。serve是前台命令，中文打开 [http://127.0.0.1:7070/?lang=zh](http://127.0.0.1:7070/?lang=zh)，英文打开 `/?lang=en`。顶部中文/English链接允许随时切换，会刷新页面。查询语言覆盖旧Cookie，API文字按当前浏览器语言返回，其他数据不变。

代理保持对应终端session，不启动可见弹窗；HTTP就绪后再报成功。用 `status --port 7070` 查询模型状态；停止用对应serve会话Ctrl+C。端口占用时选新端口，不杀其他应用。

## 已下载模型

将以下JSON另存任务目录 `local-models.json`，serve增加 `--local-models <该文件>`。启动器仅把原 AVAILABLE_MODELS 的路径替换为本地目录，模型加载仍调用原API。用户只应选择已映射模型，未映射的模型仍使用原Hub ID。

```json
{
  "kronos-small": {
    "model": "E:/Kronos-master-skills/models/Kronos-small",
    "tokenizer": "E:/Kronos-master-skills/models/Kronos-Tokenizer-base"
  }
}
```

核心依赖复用预测环境。原WebUI要求 flask==2.3.3、flask-cors==4.0.0、plotly==5.17.0；其余以快照requirements为准，Feather另需pyarrow。JSON导出在work/webui/prediction_results中，与命令行预测CSV不是同一种格式。

## 页面操作

选数据文件→加载数据→选模型及设备→加载模型→确认状态→选择窗口→调整采样参数→预测→查看图和表。默认历史400、目标120，都是数据点数，周期取决于文件。UI本身不拉取实时行情、不刷新新闻，也不会计算完整交易策略收益。

原页面刷新后，前端 modelLoaded 标记会重置；即使服务器仍保留模型，也需在页面重新点击 Load Model，才能启用 Start Prediction。这是原页面行为，不是服务丢失权重。

截图或报告引用结果时记下文件、起点、采样参数、模型、设备、原始JSON位置。不能将选中历史窗口的预测称为尚未发生的未来预测。
