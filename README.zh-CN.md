<div align="center">

# Kronos Skills—金融K线预测skills

***5个可安装的AI Agent Skills，用自然语言完成 K 线预测、历史验证、模型微调、可视化分析与预测证据审查的 AI 辅助量化分析工具***

[![Model: Kronos](https://img.shields.io/badge/Model-Kronos-176B93?style=flat-square)](https://github.com/shiyu-coder/Kronos)
[![Skills: 5](https://img.shields.io/badge/Skills-5-315B83?style=flat-square)](#skills)
[![Python: 3.10–3.12](https://img.shields.io/badge/Python-3.10%E2%80%933.12-3776AB?style=flat-square&logo=python&logoColor=white)](#setup)
[![Framework: PyTorch](https://img.shields.io/badge/Framework-PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white)](https://pytorch.org/)
[![Inference: Local](https://img.shields.io/badge/Inference-Local-25836A?style=flat-square)](#workflow)
[![License: MIT](https://img.shields.io/badge/License-MIT-52796F?style=flat-square)](Kronos-Skills-Portable/LICENSE)

Kronos Skills 为 Claude Code、Codex、Cursor 、WorkBuddy 等支持 Skills 的 AI 工具提供可复用的**金融K线预测研究能力**。本项目是**一套基于 Kronos 模型的 AI 辅助量化分析工具**，包含**5 个可独立使用、也可组合调用的 Skills**，涵盖 **股票K 线预测、历史回测、模型微调、可视化分析与预测证据审查**。预测分析功能支持**沪深 A 股、北交所、美股和港股**，并提供 **日线及 1、5、15、30、60、120 分钟 K 线预测接口**。

**该skills适合对量化交易和AI辅助投资感兴趣的人群！**

**适合金融、计算机及相关专业的学生和研究人员，用于金融时间序列预测、模型微调、量化策略回测与教学实验。**

**适合希望通过 AI 辅助量化分析，为日常投资理财提供参考的人群。**

**适合每天看着K线迷茫的你，对理财焦虑的你，适合不想总跟着别人买，希望有自己判断的你。**

**它不保证你会一夜暴富，但会让你对你的交易和理财策略越来越有信心**

**如果它能提高你选股的正确概率，那它就已经发挥出它应有的作用了。**

如果你认为这个skills做的不好也没有关系，因为我们本身并不优秀，但我们正在努力让自己成为最小的作用单元。

</div>

---

<a id="overview"></a>

## 📈 项目简介

Kronos Skills 是围绕**清华大学团队开发的金融 K 线模型而构建的AI 辅助量化分析工具**：

**预测K线用的是 Kronos-small模型，skills 的作用是组织和执行整个流程，AI来理解你的需求，按skills 来操作工具，处理报错，最后整理结果并解释。**

**因此你用自然语言提出需求，AI 就能按照skills相应流程获取和核验行情、调用模型预测，以及完成历史回测、模型微调、可视化分析和预测证据审查，把模型能力变成可以直接使用的研究流程**

**[shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos) 清华大学团队开发的Kronos金融K线预测模型。**

| 已训练模型 | 参数量 | 上下文长度 |
| :--- | ---: | ---: |
| Kronos-mini | 4.1M | 2,048 |
| **Kronos-small** | **24.7M** | **512** |
| Kronos-base | 102.3M | 512 |

同一只股票，随着最新行情、输入区间和采样参数的变化，预测结果也可能不同。因此，这套 Skills 的价值，需要通过持续的历史检验和实际跟踪来判断。从概率意义上讲，**如果它能帮助你更高效地分析金融K线，并在验证中提高选股和判断的胜率，那它就已经发挥出它应有的作用了**

***本 skills 当前仅封装提供 Kronos-small 的本地预训练权重及其配套 Tokenizer，目的是降低硬件门槛，让大部分用户更方便地使用。** Kronos-small 具有约 2,470 万参数、512 根 K 线的上下文长度，在模型规模与运行资源需求之间取得平衡。*

<a id="skills"></a>

## 🧩 五个技能

从真实行情数据出发，通过五个可独立使用、也可组合调用的 Skills，完成涵盖 K 线预测、历史回测、模型微调、可视化分析与证据审查的金融K线预测研究工作流。

| 技能 | 功能 | 什么时候用 |
| :--- | :--- | :--- |
| **`kronos-kline—predict`** | **从历史行情预测未来日线或分钟 K 线** | **预测未来K线趋势、涨跌** |
| **`kronos-backtest`** | 使用原项目入口检验历史表现，比较策略和基准 | **评估模型或策略在过去的表现效果** |
| **`kronos-training`** | 用自己的行情微调 Tokenizer 和 Predictor | **训练模型适配某一支股票** |
| **`kronos-webui`** | 在中文／英文网页里加载数据、调整参数、对比预测与实际 | **在网页里操作模型、调整参数，直观看预测与实际行情的差异** |
| **`kronos-buffett-munger-review`** | 借鉴巴菲特与芒格的思考方式，审查预测是否有足够依据，不代表预测准确率 | **审查在模型已经给出预测、审查预测是否有足够依据** |

### **🎯 K线预测：从历史行情预测未来 K 线**

**`kronos-kline-predict` 支持日线及 1、5、15、30、60、120 分钟接口。预测时，AI会按skills要求主动寻找并核验数据：**

| **市场**      | **获取方式**         | **行情来源**                       | **说明**                                 |
| :------------ | :------------------- | :--------------------------------- | :--------------------------------------- |
| **沪深 A 股** | **AKShare**          | **新浪财经、东方财富等**           | **核验所需周期、历史范围与数据完整性**   |
| **北交所**    | **北交所市场适配器** | **北交所官方证券名录、东方财富等** | **逐只核验证券代码及数据源覆盖情况**     |
| **美股**      | **yfinance**         | **Yahoo Finance、东方财富等**      | **核验交易时区、常规交易时段及历史范围** |
| **港股**      | **yfinance**         | **Yahoo Finance、东方财富等**      | **核验证券代码、午间休市及半日交易安排** |

<h2>📷 两图对比</h2>
<p>左侧为东方财富盘口截图，右侧为日线查询结果截图。点击图片可查看原图。</p>

<table>
  <thead>
    <tr>
      <th width="30%">东方财富 · 盘口截图</th>
      <th width="70%">日线查询 · 结果截图</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td width="30%" valign="top" align="center">
        <a href="./figures/maotai-eastmoney.jpg"><img src="./figures/maotai-eastmoney.jpg" alt="东方财富贵州茅台盘口截图" width="100%" /></a>
      </td>
      <td width="70%" valign="top" align="center">
        <a href="./figures/maotai-daily-query.png"><img src="./figures/maotai-daily-query.png" alt="贵州茅台2026年9月28日日线查询结果截图" width="100%" /></a>
      </td>
    </tr>
  </tbody>
</table>

<h3>🔍 日线查询结果大图</h3>
<p align="center">
  <a href="./figures/maotai-daily-query.png"><img src="./figures/maotai-daily-query.png" alt="贵州茅台日线查询结果大图" width="1200" /></a>
</p>
**获取市场行情的准确率达到100%，也支持读取用户提供的 CSV 文件。**

**预测前会检查证券身份、时间戳、复权口径、价格与成交量单位、交易日历、缺失 K 线和 OHLC 关系。**

**具体工作流程**

```text
股票、市场、日期与周期 → 获取或读取行情 → 核验数据和交易时间
→ 准备模型输入 → Kronos 推理 → 检查预测结果 → 图表、表格与报告
```

### **🕰️ 回归测试：在历史数据上检验表现**

**`kronos-backtest` 复用原项目 Qlib、CSV 策略及回归测试入口。真实模型回测、随机历史示例、程序输出回归测试是不同任务。 随机示例不能当作模型效果，回归测试通过也不代表市场预测准确。**

**原 CSV 策略存在缺失实际价格时使用预测价格等限制，执行时必须披露。需要评估真实模型和组合策略时，优先选择 Qlib 入口并核对实际数据、费用和基准配置。**

**具体工作流程**

```text
历史数据、模型或已有预测 → 选择回测入口 → 创建独立工作副本
→ 检查依赖与配置 → 执行原项目流程 → 核对指标、基准与日志
```

### **🧠 模型训练：利用自身数据进行微调**

**`kronos-training` 支持 Qlib 数据准备、Tokenizer／Predictor 单独微调、CSV 顺序训练及原项目多 GPU 入口。保留原源码快照与已有权重，训练写入新的实验目录。训练完成后应重新做预测和历史验证；训练损失降低不等于交易效果提高。**

**具体工作流程**

```text
训练数据与预训练权重 → 按时间划分训练／验证／测试集
→ 创建实验副本并检查配置 → 微调 Tokenizer／Predictor → 保存 checkpoint → 再做预测验证
```

### **🖥️ 创建网页：在网页里操作并对比结果**

**`kronos-webui` 提供中英文界面，加载本地 CSV／Feather，选择模型、设备和采样参数。**

**启动时选择语言；普通预测和结果图无需启动网页。**

**具体工作流程**

```text
选择中文／英文 → 创建网页工作副本 → 导入本地数据 → 检查并启动服务
→ 选择模型和设备 → 调整窗口与参数 → 预测、查看图表并保存结果
```

### **⚖️ 证据审查：审查预测是否有足够依据**

**`kronos-buffett-munger-review` 将股神沃伦·巴菲特与查理·芒格的思考方式蒸馏为可调用的预测审查技能，审查预测的证据支持度，不代表预测准确率。**

**它将巴菲特式的证据判断与芒格式的逆向思考，落实到数据可靠性、历史依据、结构错误、采样稳定性和表述是否过度确定的检查上。这里的“蒸馏”指思考方式的流程化整理，不是对两位人物进行模型训练，也不代表本人或其机构的意见。**

**具体工作流程**

```text
已有预测及当时可见的材料 → 核对数据口径和信息边界
→ 巴菲特式证据判断＋芒格式逆向检查 → 五项评分及硬门槛 → 对话输出审查意见
```

| **维度** | **满分** |
| :--- | ---: |
| **数据完整性与口径一致性** | **30** |
| **历史方向、幅度和基准比较** | **20** |
| **OHLC 与交易时间结构** | **20** |
| **多次采样稳定性** | **20** |
| **表述校准** | **10** |

**总分是 100 分制证据支持度，不代表预测准确率。审查在模型已经给出预测、目标行情尚未发生时使用。数据边界不清、OHLC 结构错误、只有单次采样等情况会触发限分规则。该技能只在对话中输出审查，不生成附件，不读取目标时段后来发生的行情。**

**<a id="markets"></a>**

## **✨ 核心特性**

| **能力**             | **说明**                                                     |
| -------------------- | ------------------------------------------------------------ |
| **跨 Agent 使用**    | **同一安装器支持 Claude Code、Cursor、Codex、Gemini CLI、OpenClaw 、WorkBuddy和 OpenCode** |
| **按需安装**         | **可安装完整集合、单个分类或指定 Skill**                     |
| **项目级隔离**       | **可选择全局安装，也可仅安装到当前项目**                     |
| **五大技能协作**     | **覆盖 K 线预测、历史回测、模型微调、可视化分析与预测证据审查** |
| **模型推理**         | **随包提供 Kronos-small 与配套 Tokenizer 权重，模型可存放在任意可读目录，由 Agent 核验并配置路径** |
| **调用行情数据接口** | **直接调用行情数据接口，并不是找网页、新闻或搜索摘要，再从中整理信息。提高取数的准确性、可追溯性和效率** |

**<a id="setup"></a>**

## **🚀 快速开始**

### **📥 按系统下载技能包**

| **系统** | **独立压缩包（可解压到任意目录）** | **大小** |
| :--- | :--- | ---: |
| **Windows 64位** | **[Kronos-Skills-Windows.zip](Kronos-Skills-Windows.zip)** | **约119 MiB** |
| **macOS Apple Silicon／Intel** | **[Kronos-Skills-macOS.zip](Kronos-Skills-macOS.zip)** | **约138 MiB** |

**两份都包含五个技能和配套模型权重。将压缩包完整解压到任意目录后，将skills放到：**

#### 🤖 支持的 Agent

| Agent       | `--tool` 参数 | 全局安装目录                         | 项目级安装目录                 |
| ----------- | :-----------: | ------------------------------------ | ------------------------------ |
| Claude Code |   `claude`    | `~/.claude/skills/<技能名>`          | `.claude/skills/<技能名>`      |
| Cursor      |   `cursor`    | `~/.cursor/skills/<技能名>`          | `.cursor/skills/<技能名>`      |
| Codex       |    `codex`    | `~/.codex/skills/<技能名>`           | `.codex/skills/<技能名>`       |
| Gemini CLI  |   `gemini`    | `~/.gemini/skills/<技能名>`          | `.gemini/skills/<技能名>`      |
| OpenClaw    |  `openclaw`   | `~/.openclaw/skills/<技能名>`        | `.openclaw/skill<技能名>s/`    |
| OpenCode    |  `opencode`   | `~/.config/opencode/skills/<技能名>` | `.opencode/skills/<技能名>`    |
| WorkBuddy   |  `WorkBuddy`  | `~/.workbuddy/skills/<技能名>`       | `~/.workbuddy/skills/<技能名>` |
| ...         |      ...      | ...                                  | ...                            |

`<技能名>`包括文件夹**`kronos-kline—predict`**、**`kronos-backtest`**、**`kronos-training`**、**`kronos-webui`**、**`kronos-buffett-munger-review`**

**</details>**

### ▶️使用

#### **1.让AI一键安装环境依赖（按照👇的步骤不用担心现在找C盘默认路径）**

**输入：**

```text
使用 kronos-kline-predict，预测沃尔玛 WMT 下一个交易日的5分钟走势。
使用美股扩展版，标注美东时间，并输出图、逐根表格和中文报告。

我已将技能包解压到 D:\Kronos-Skills-Windows。（换成你的具体目录）

请以这个文件夹为工作区，按照包内说明准备环境。
将项目使用的 Python 运行时、虚拟环境、模型权重和下载缓存放在这个文件夹内，预测结果保存到 outputs 文件夹。

先检查已有环境、依赖和模型，复用兼容的安装，只补齐缺少的部分。
环境准备完成后，运行包内检查，确认模型和设备可用，再执行上面的沃尔玛预测任务。

完成后告诉我环境位置，以及预测图、逐根表格和中文报告的保存位置。
```

把上面这段话给Agent，模型会开始推理，依赖  PyTorch、NumPy、pandas、einops、huggingface_hub、safetensors、Matplotlib、tqdm  缺少时Agent会按包内清单安装依赖。

#### **2.用命令行安装**

详见 [Windows命令行安装步骤](./Windows命令行安装步骤.md)。

**<a id="examples"></a>**

## **💬 使用示例**

| **你想做什么** | **可以这样说** |
| :--- | :--- |
| **沪深股票预测** | **“用 Kronos 预测贵州茅台未来5个交易日的日线，先核验最新行情。”** |
| **北交所预测** | **“用 Kronos 预测这只北交所股票下一个交易日的5分钟走势，先核验现行代码和数据源覆盖。”** |
| **美股预测** | **“使用美股扩展版预测 WMT 下一个交易日的5分钟走势，时间标成美东时间。”** |
| **港股预测** | **“使用港股扩展版预测腾讯 0700.HK 下一个完整交易日的5分钟走势，午休分开。”** |
| **历史验证** | **“用 kronos-backtest 的真实 Qlib 入口，检查这段历史上的策略表现和指数基准，说明费用口径。”** |
| **模型微调** | **“用 kronos-training 检查这份 CSV 的训练条件，在新实验目录微调模型，保留原权重。”** |
| **打开网页** | **“用 kronos-webui 打开中文界面，加载这份已有行情文件。”** |
| **审查预测** | **“用 kronos-buffett-munger-review 审查刚才的预测，给证据支持度，不读取目标时段后来的行情。”** |

**</details>**

## **🙏 来源与致谢**

**本项目基于 Kronos: A Foundation Model for the Language of Financial Markets。**

| **资源** | **链接** |
| :--- | :--- |
| **上游模型与代码** | **[shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos)** |
| **论文** | **[arXiv:2508.02739](https://arxiv.org/abs/2508.02739)** |
| **模型权重** | **[Hugging Face · NeoQuasar](https://huggingface.co/NeoQuasar)** |
| **上游演示** | **[Kronos Demo](https://shiyu-coder.github.io/Kronos-demo/)** |

**Kronos 将连续的金融 K 线数据转换为离散 token，再用自回归 Transformer 生成未来序列。**

**本技能沿用配套 Tokenizer 与预测模型，模型参数见[项目简介](#overview)，具体权重版本以下载记录和运行参数为准。较大模型不保证在每个市场或周期上更准确。**

**感谢上游 Kronos 作者，以及 PyTorch、Qlib、AKShare、yfinance、exchange_calendars、Matplotlib 和 Plotly 等开源项目。**

## **📄 许可证说明**

本项目采用 MIT 许可证。

