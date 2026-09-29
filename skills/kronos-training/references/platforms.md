# macOS 与可移植路径

本技能的脚本通过自身位置解析资源，无需开发者机器的E/C盘目录。
Mac使用自己的Python虚拟环境：`python3.11 -m venv .venv-kronos`，
解释器在`.venv-kronos/bin/python`；Windows在`.venv-kronos/Scripts/python.exe`。
完整分发包的MACOS.zh-CN.md提供环境安装、模型路径和各技能命令。
独立安装技能时按实际位置调用脚本，不把文档中的Windows路径当成固定依赖。

Mac的CSV顺序训练选择原CPU流程，YAML显式设置device.use_cuda=false、training.num_workers=0；
数据、模型和输出路径改为当前Mac上的路径。先stage到新目录，再check，最后run。
原Qlib训练硬编码CUDA/NCCL，Mac不支持该入口；不宣称已增加MPS训练。
