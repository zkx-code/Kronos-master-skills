# Windows 64位 包内环境准备

本技能属于Kronos-Skills-Windows分发包。先确定包根目录（包含PACKAGE.json、models、setup_env.py）。
已有正常环境则直接复用，先运行doctor.py；证据审查仅需要读取结果，不必安装模型环境。
只运行普通预测无需启动WebUI。原源码快照保持不变。

包内附带 `tools/windows-x64/uv.exe`，来源为Astral官方uv在PyPI发布的wheel，SHA256和许可证位于相邻文件。
Python采用uv管理的CPython 3.12.13，首次自动下载，不需要用户先装Python。
依赖从正常Python包索引安装，不自动安装系统驱动、不提升系统权限。

## 尚无运行环境时

```powershell
$bundle = (Get-Location).Path
$env:UV_CACHE_DIR = Join-Path $bundle '.cache/uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $bundle '.runtime/python'
& "$bundle/tools/windows-x64/uv.exe" run --no-project --no-config --no-env-file --managed-python --python 3.12.13 "$bundle/setup_env.py" --extras webui csv-training
# setup_env.py创建 .venv-kronos；后续运行这个环境的Python。
& "$bundle/.venv-kronos/Scripts/python.exe" "$bundle/doctor.py" --smoke
```


setup_env.py遇到已有虚拟环境会停止，不能盲目重复创建；先检查或明确选择新 --venv 路径。
只需要预测时可以省略 --extras。Qlib工作流需要额外准备pyqlib等依赖和数据，显式选 --extras qlib。
不能把装完默认预测环境描述为完成训练或回测准备。

## 模型与入口

默认small会发现包根目录的models目录（与skills目录同级）。单独安装技能后则显式指定 `--models-dir /实际包根目录/models`。
所有脚本通过实际包目录定位，文档中的原开发盘符不是固定依赖。
已指定MPS/CUDA而失败时报告原因，不自动换CPU或随机初始化。
Mac CSV训练使用原CPU入口；原CUDA/NCCL分布式训练不适用于Mac。
Windows GPU版本的PyTorch由用户硬件和驱动决定；先验证可用设备，不承诺默认安装一定提供CUDA。
