# macOS 与可移植路径

本技能的脚本通过自身位置解析资源，无需开发者机器的E/C盘目录。
Mac使用自己的Python虚拟环境：`python3.11 -m venv .venv-kronos`，
解释器在`.venv-kronos/bin/python`；Windows在`.venv-kronos/Scripts/python.exe`。
完整分发包的MACOS.zh-CN.md提供环境安装、模型路径和各技能命令。
独立安装技能时按实际位置调用脚本，不把文档中的Windows路径当成固定依赖。

证据审查读取现有预测材料，在对话内给出评分，不依赖CUDA/MPS或Windows环境。
它无需重新训练或加载模型；用当前Mac上可读的预测文件路径即可。
