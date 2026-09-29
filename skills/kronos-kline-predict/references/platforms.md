# macOS 与可移植路径

本技能的脚本通过自身位置解析资源，无需开发者机器的E/C盘目录。
Mac使用自己的Python虚拟环境：`python3.11 -m venv .venv-kronos`，
解释器在`.venv-kronos/bin/python`；Windows在`.venv-kronos/Scripts/python.exe`。
完整分发包的MACOS.zh-CN.md提供环境安装、模型路径和各技能命令。
独立安装技能时按实际位置调用脚本，不把文档中的Windows路径当成固定依赖。

推理默认auto依次检测CUDA/MPS/CPU；显式选择设备失败时报告错误，不自动改设备。
Apple Silicon可用`--device mps`，Intel Mac使用`--device cpu`。
使用随附权重时传`--models-dir /实际解压目录/models`，或保留skills与models为同级目录。
MPS分支已作逻辑验证，尚无实体Mac推理实测；使用分发包doctor.py --device mps --smoke在目标机确认。
