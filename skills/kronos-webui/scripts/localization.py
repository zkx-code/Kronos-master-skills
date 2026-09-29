"""Presentation-only localization for the hash-verified original WebUI."""
import json
import re

# Exact UI text, including original JS template literals. Data keys, paths and prices stay intact.
ZH = {
    'Kronos Financial Prediction Web UI':'Kronos 金融预测界面',
    'AI-based financial K-line data prediction analysis platform':'基于 AI 的金融 K 线预测与分析平台',
    'Control Panel':'控制面板', 'Select Model:':'选择模型：',
    'Please load available models first':'请先加载可用模型', 'Select the Kronos model to use':'选择要使用的 Kronos 模型',
    'Select Device:':'选择运行设备：', 'CUDA (NVIDIA GPU)':'CUDA（NVIDIA 显卡）', 'MPS (Apple Silicon)':'MPS（Apple 芯片）',
    'Select the device to run the model on':'选择模型运行设备', 'Model status information':'模型状态',
    'Load Model':'加载模型', 'Select Data File:':'选择数据文件：',
    'Please load data file list first':'请先加载文件列表', 'Select K-line data file from data directory':'从数据目录选择 K 线文件',
    'Load Data':'加载数据', 'Data Information':'数据信息', 'Rows:':'行数：', 'Columns:':'列数：',
    'Time Range:':'时间范围：', 'Price Range:':'价格范围：', 'Time Frequency:':'数据周期：', 'Prediction Columns:':'预测字段：',
    'Time Window Selection':'时间窗口选择', 'Start: --':'开始：--', 'End: --':'结束：--',
    'Window Size: 400+120=520 data points':'窗口：400＋120＝520 个数据点',
    'Earliest':'最早', 'Latest':'最晚',
    'Drag slider to select time window position for 520 data points, green area represents fixed 400+120 data point range':'拖动滑块选择窗口位置；绿色区域为固定的 400＋120 个数据点范围',
    'Lookback Window Size:':'历史窗口长度：', 'Fixed at 400 data points':'固定为 400 个数据点',
    'Prediction Length:':'预测长度：', 'Fixed at 120 data points':'固定为 120 个数据点',
    'Prediction Temperature (T):':'采样温度（T）：',
    'Controls prediction randomness, higher values make predictions more diverse, lower values make predictions more conservative':'控制采样随机性：值越高越多样，值越低越集中',
    'Nucleus Sampling Parameter (top_p):':'核采样参数（top_p）：',
    'Controls prediction diversity, higher values consider broader probability distributions':'控制采样范围：值越高，考虑的概率分布范围越广',
    'Sample Count:':'采样条数：',
    'Generate multiple prediction samples to improve quality (recommended 1-3)':'生成并平均多条预测路径（原界面建议 1–3 条；不保证更准确）',
    'Start Prediction':'开始预测', 'Processing, please wait...':'处理中，请稍候……',
    'Prediction Results Chart':'预测结果图', 'Prediction vs Actual Data Comparison':'预测与实际数据对比',
    'Prediction Type:':'预测类型：', 'Comparison Data:':'对比数据：',
    'Mean Absolute Error':'平均绝对误差', 'Root Mean Square Error':'均方根误差',
    'Mean Absolute Percentage Error':'平均绝对百分比误差', 'Price Units':'价格单位',
    'Detailed Comparison Data:':'逐根对比数据：',
    '>Time<':'>时间<', 'Actual Open':'实际开盘', 'Predicted Open':'预测开盘',
    'Actual High':'实际最高', 'Predicted High':'预测最高', 'Actual Low':'实际最低', 'Predicted Low':'预测最低',
    'Actual Close':'实际收盘', 'Predicted Close':'预测收盘',
    'Please select model':'请选择模型', 'Please select a model to load':'请选择要加载的模型',
    'Please select data file':'请选择数据文件', 'Please select a data file to load':'请选择要加载的数据文件',
    'Please load data file first':'请先加载数据文件', 'Please load model first':'请先加载模型',
    'Failed to load available models':'可用模型列表加载失败', 'Failed to load data file list':'数据文件列表加载失败',
    'Model available but not loaded':'模型可用，尚未加载', 'Model library not available':'模型库不可用',
    'Kronos model library not available, will use simulated prediction':'Kronos 模型库不可用，请先修复依赖',
    'Time window slider not initialized':'时间窗口滑块尚未初始化',
    'Model loading failed:':'模型加载失败：', 'Data loading failed:':'数据加载失败：', 'Prediction failed:':'预测失败：',
    'Model loaded: ${status.current_model.name} on ${status.current_model.device}':'模型已加载：${status.current_model.name}，设备 ${status.current_model.device}',
    '${dataInfo.start_date} to ${dataInfo.end_date}':'${dataInfo.start_date} 至 ${dataInfo.end_date}',
    'Start: ${startDate.toLocaleDateString()}':'开始：${startDate.toLocaleDateString("zh-CN")}',
    'End: ${endDate.toLocaleDateString()}':'结束：${endDate.toLocaleDateString("zh-CN")}',
    'Window Size: 400 + 120 = 520 data points (fixed)':'窗口：400＋120＝520 个数据点（固定）',
    'Insufficient data, need at least ${windowSize} data points, currently only ${totalRows} available':'数据不足：至少需要 ${windowSize} 个数据点，当前只有 ${totalRows} 个',
    '${result.actual_data.length} actual data points':'${result.actual_data.length} 个实际数据点',
    'Historical Data (400 data points)':'历史数据（400 个数据点）',
    'Prediction Data (120 data points)':'预测数据（120 个数据点）',
    'Actual Data (120 data points)':'实际数据（120 个数据点）',
    'Kronos Financial Prediction Results - 400 Historical Points + 120 Prediction Points vs 120 Actual Points':'Kronos 预测对比：400 根历史＋120 根预测与实际数据',
    'Lightweight model, suitable for fast prediction':'轻量模型，适合快速预测',
    'Small model, balanced performance and speed':'小型模型，兼顾运行速度与模型规模',
    'Base model, provides better prediction quality':'基础模型，模型规模更大',
    'Kronos model loaded and available':'Kronos 模型已加载，可使用',
    'Kronos model available but not loaded':'Kronos 模型库可用，尚未加载权重',
    'Kronos model library not available, please install related dependencies':'Kronos 模型库不可用，请安装相关依赖',
    'Kronos model library not available':'Kronos 模型库不可用',
    'Kronos model not loaded, please load model first':'尚未加载 Kronos 模型，请先加载',
    'File path cannot be empty':'文件路径不能为空', 'Unsupported file format':'不支持此文件格式',
    'Unsupported model:':'不支持的模型：', 'Failed to load file:':'文件加载失败：', 'Failed to load data:':'数据加载失败：',
    'Missing required columns:':'缺少必要字段：', 'Kronos model prediction failed:':'Kronos 模型预测失败：',
    'Expected a JSON object':'请求必须是 JSON 对象',
    'Select an imported file from this work directory data folder':'请选择当前工作目录 data 下已导入的文件',
    'Real timestamps required; generated timestamp fallback is not allowed':'数据缺少真实时间戳，请先补齐来源数据',
    'Original UI requires at least 400+120=520 rows':'原界面至少需要 400＋120＝520 行数据',
    'Missing OHLC columns':'缺少开盘、最高、最低或收盘字段',
    'Invalid OHLC values':'开高低收存在无效数值', 'Invalid OHLC relations':'开高低收价格关系异常',
    'Timestamps must be complete, increasing and unique':'时间戳必须完整、递增且唯一',
}
PATTERN=re.compile(r'(?<![A-Za-z0-9_])(?:'+'|'.join(re.escape(k) for k in sorted(ZH,key=len,reverse=True))+')')


def translate(text):
    exact={
        'Time':'时间','Price':'价格','Unknown':'未知',
        'open':'开盘','high':'最高','low':'最低','close':'收盘','volume':'成交量','amount':'成交额',
    }
    if text in exact: return exact[text]
    patterns=[
        (r'^Successfully loaded data, total (\d+) rows$',r'数据加载成功，共 \1 行'),
        (r'^Model loaded successfully: (.+) on (.+)$',r'模型加载成功：\1，设备 \2'),
        (r'^Prediction completed, generated (\d+) prediction points(?:, including (\d+) actual data points for comparison)?$',
         lambda m:f'预测完成，生成 {m[1]} 个预测点'+(f'，与 {m[2]} 个实际数据点对比' if m[2] else '')),
        (r'^(\d+) (seconds|minutes|hours|days)$',lambda m:m[1]+' '+{'seconds':'秒','minutes':'分钟','hours':'小时','days':'天'}[m[2]]),
        (r'^Insufficient data length, need at least (\d+) rows$',r'数据不足，至少需要 \1 行'),
        (r'^Insufficient data from start time (.+), need at least (\d+) data points, currently only (\d+) available$',r'从 \1 起数据不足：需要 \2 个数据点，目前只有 \3 个'),
        (r'^Kronos model prediction \(within selected window: first (\d+) data points for prediction, last (\d+) data points for comparison, time span: (.+)\)$',r'Kronos 历史窗口预测（前 \1 根输入，后 \2 根实际对比，时间跨度：\3）'),
        (r'^Kronos model prediction \(latest data\)$','Kronos 模型预测（原界面默认窗口）'),
    ]
    for pattern,replacement in patterns:
        if re.match(pattern,text): return re.sub(pattern,replacement,text)
    return PATTERN.sub(lambda m:ZH[m[0]],text)


def localize_payload(payload):
    """Only human-facing metadata and chart labels; preserve OHLC, times, keys and paths."""
    def visit(value,key=''):
        if isinstance(value,dict): return {k:visit(v,k) for k,v in value.items()}
        if isinstance(value,list): return [visit(v,key) for v in value]
        if isinstance(value,str) and key in ('message','error','description','prediction_type','timeframe'):
            return translate(value)
        return value
    result=visit(payload)
    if isinstance(result,dict) and isinstance(result.get('chart'),str):
        chart=json.loads(result['chart'])
        for trace in chart.get('data',[]):
            if 'name' in trace: trace['name']=translate(trace['name'])
        layout=chart.get('layout',{})
        for obj in (layout,layout.get('xaxis',{}),layout.get('yaxis',{})):
            title=obj.get('title')
            if isinstance(title,dict) and 'text' in title: title['text']=translate(title['text'])
            elif isinstance(title,str): obj['title']=translate(title)
        result['chart']=json.dumps(chart,ensure_ascii=False)
    return result


def localize_html(html,language):
    if language=='zh':
        html=PATTERN.sub(lambda m:ZH[m[0]],html)
        # These are display values only, not the field names consumed by prediction.
        html=html.replace("dataInfo.prediction_columns.join(', ')","dataInfo.prediction_columns.map(c => ({open:'开盘',high:'最高',low:'最低',close:'收盘',volume:'成交量',amount:'成交额'}[c] || c)).join('、')")
    html=html.replace('<html lang="zh-CN">',f'<html lang="{"zh-CN" if language=="zh" else "en"}">')
    label='界面语言' if language=='zh' else 'Interface language'
    nav=f'<nav aria-label="{label}" style="text-align:right;margin:0 0 12px;color:white;font-size:15px">{label}：<a href="/?lang=zh" lang="zh-CN" style="color:white" aria-current="{"page" if language=="zh" else "false"}">中文</a> · <a href="/?lang=en" lang="en" style="color:white" aria-current="{"page" if language=="en" else "false"}">English</a></nav>'
    return html.replace('<div class="container">','<div class="container">'+nav,1)
