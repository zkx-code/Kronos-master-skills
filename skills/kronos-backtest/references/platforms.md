# macOS 与可移植路径

本技能的脚本通过自身位置解析资源，无需开发者机器的E/C盘目录。
Mac使用自己的Python虚拟环境：`python3.11 -m venv .venv-kronos`，
解释器在`.venv-kronos/bin/python`；Windows在`.venv-kronos/Scripts/python.exe`。
完整分发包的MACOS.zh-CN.md提供环境安装、模型路径和各技能命令。
独立安装技能时按实际位置调用脚本，不把文档中的Windows路径当成固定依赖。

Mac的Qlib回测默认device=cpu；须先准备pyqlib依赖、市场数据和匹配checkpoint。
CSV策略、随机示例和模型回归沿用原入口及原有局限。
原始快照中的路径和字体示例不是本机自动配置，需要在允许修改的工作副本配置中指定。
