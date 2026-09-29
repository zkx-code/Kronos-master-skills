# macOS 与可移植路径

本技能的脚本通过自身位置解析资源，无需开发者机器的E/C盘目录。
Mac使用自己的Python虚拟环境：`python3.11 -m venv .venv-kronos`，
解释器在`.venv-kronos/bin/python`；Windows在`.venv-kronos/Scripts/python.exe`。
完整分发包的MACOS.zh-CN.md提供环境安装、模型路径和各技能命令。
独立安装技能时按实际位置调用脚本，不把文档中的Windows路径当成固定依赖。

页面可选择CPU或MPS；MPS仅用于系统和PyTorch确实支持的设备。启动前仍按技能要求选择中/英文。
--local-models JSON内的相对模型路径按JSON所在目录解析，适用于移动整个分发包。
用Control+C停止前台Flask服务；不依赖PowerShell或Windows进程命令。
