# 内容风险模式检测工具

该项目是一个用于分析多轮对话中潜在内容风险的工具，能够检测多种风险模式，包括：显性风险组合类、隐喻协作类、信息拼图类、时序依赖类、角色特性利用类和文化规避类。

## 功能特点

- 从维基百科爬取风险相关词汇和内容
- 构建全面的风险模式库（50种模式）
- 检测多轮对话中的风险内容
- 支持命令行和API两种调用方式
- 生成详细的风险分析报告

## 安装方法

```bash
# 克隆仓库
git clone https://github.com/yaozhongjiang/wiki-content-risk-analyzer.git

# 安装依赖
cd wiki-content-risk-analyzer
pip install -r requirements.txt

# 安装包（开发模式）
pip install -e .
```

## 使用方法

### 1. 爬取维基百科内容

```bash
python -m src.main scrape --topics "个人隐私" "网络安全" "社会工程学" --lang zh --output data/vocabulary.json
```

### 2. 构建风险模式库

```bash
python -m src.main build --vocabulary data/vocabulary.json --output data/risk_patterns.json
```

### 3. 分析会话风险

```bash
python -m src.main analyze --conversation examples/conversation.json --patterns data/risk_patterns.json --vocabulary data/vocabulary.json --output results/analysis_result.json
```

### 4. 启动API服务

```bash
python -m src.main api --host 127.0.0.1 --port 8000
```

然后可以通过HTTP请求调用API：

```bash
curl -X POST -H "Content-Type: application/json" -d @examples/conversation.json http://localhost:8000/api/analyze
```

## 风险模式库

本项目实现了全面的风险模式检测，包括六大类共50种风险模式：

1. **显性风险组合类（10种）** - 检测多轮对话中分散的危险内容组合
2. **隐喻协作类（8种）** - 检测通过隐喻、类比等方式隐藏的风险内容
3. **信息拼图类（12种）** - 检测分散在多轮对话中的信息拼图
4. **时序依赖类（10种）** - 检测随时间推移升级的危险建议
5. **角色特性利用类（6种）** - 检测利用角色权威性或心理特性诱导的风险
6. **文化规避类（4种）** - 检测通过文化差异规避检测的风险内容

## 典型风险模式

- **P1: 暴力诱导分步教学** - 分步骤教授危险物品制作，每个步骤提供部分信息
- **P2: 金融诈骗角色协作** - 通过多轮对话建立信任链条，最终诱导金融诈骗
- **P3: 隐私数据收集** - 跨多轮对话收集分散的个人隐私信息
- **P4: 药物滥用引导** - 随时间推移升级药物使用的危险建议
- **P5: 假冒权威建议** - 利用专业角色权威性提供不当医疗、法律等建议
- **P6: 歧视性内容传播** - 通过统计数据伪装等方式传播偏见和歧视内容

## 许可证

MIT