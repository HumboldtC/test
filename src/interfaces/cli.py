import argparse
import json
import logging
import os
import sys

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.scraper.wiki_scraper import WikiScraper
from src.risk_analyzer.pattern_builder import PatternBuilder
from src.risk_analyzer.risk_detector import RiskDetector
from src.risk_analyzer.conversation_analyzer import ConversationAnalyzer
from src.data.data_manager import DataManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="内容风险分析工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # 爬取维基百科内容
    scrape_parser = subparsers.add_parser("scrape", help="从维基百科爬取内容")
    scrape_parser.add_argument("--topics", "-t", nargs="+", required=True, help="要爬取的主题列表")
    scrape_parser.add_argument("--lang", "-l", default="zh", choices=["zh", "en"], help="语言 (默认: zh)")
    scrape_parser.add_argument("--output", "-o", default="data/vocabulary.json", help="输出文件路径 (默认: data/vocabulary.json)")
    
    # 构建风险模式库
    build_parser = subparsers.add_parser("build", help="构建风险模式库")
    build_parser.add_argument("--vocabulary", "-v", help="词汇库文件路径")
    build_parser.add_argument("--output", "-o", default="data/risk_patterns.json", help="输出文件路径 (默认: data/risk_patterns.json)")
    
    # 分析会话
    analyze_parser = subparsers.add_parser("analyze", help="分析会话风险")
    analyze_parser.add_argument("--conversation", "-c", required=True, help="会话文件路径")
    analyze_parser.add_argument("--patterns", "-p", default="data/risk_patterns.json", help="风险模式库文件路径 (默认: data/risk_patterns.json)")
    analyze_parser.add_argument("--vocabulary", "-v", default="data/vocabulary.json", help="词汇库文件路径 (默认: data/vocabulary.json)")
    analyze_parser.add_argument("--output", "-o", help="输出文件路径")
    
    # 爬取并分析
    full_parser = subparsers.add_parser("full", help="爬取内容并分析会话")
    full_parser.add_argument("--topics", "-t", nargs="+", required=True, help="要爬取的主题列表")
    full_parser.add_argument("--lang", "-l", default="zh", choices=["zh", "en"], help="语言 (默认: zh)")
    full_parser.add_argument("--conversation", "-c", required=True, help="会话文件路径")
    full_parser.add_argument("--output", "-o", help="输出文件路径")
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 确保数据目录存在
    os.makedirs("data", exist_ok=True)
    
    if args.command == "scrape":
        # 爬取维基百科内容
        scrape_wiki(args.topics, args.lang, args.output)
    
    elif args.command == "build":
        # 构建风险模式库
        build_patterns(args.vocabulary, args.output)
    
    elif args.command == "analyze":
        # 分析会话
        analyze_conversation(args.conversation, args.patterns, args.vocabulary, args.output)
    
    elif args.command == "full":
        # 爬取内容并分析会话
        voc_file = "data/vocabulary.json"
        pat_file = "data/risk_patterns.json"
        
        # 1. 爬取维基百科内容
        scrape_wiki(args.topics, args.lang, voc_file)
        
        # 2. 构建风险模式库
        build_patterns(voc_file, pat_file)
        
        # 3. 分析会话
        analyze_conversation(args.conversation, pat_file, voc_file, args.output)
    
    else:
        parser.print_help()

def scrape_wiki(topics, lang, output):
    """爬取维基百科内容"""
    logger.info(f"开始爬取主题: {', '.join(topics)}, 语言: {lang}")
    
    scraper = WikiScraper(base_url=f"https://{lang}.wikipedia.org/wiki/")
    result = scraper.batch_scrape(topics, lang)
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    
    # 保存爬取结果
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
    
    logger.info(f"爬取完成，结果已保存到: {output}")
    return output

def build_patterns(vocabulary_file, output):
    """构建风险模式库"""
    logger.info("开始构建风险模式库")
    
    # 加载词汇库
    vocabulary_data = None
    if vocabulary_file:
        try:
            with open(vocabulary_file, 'r', encoding='utf-8') as f:
                vocabulary_data = json.load(f)
            logger.info(f"已加载词汇库: {vocabulary_file}")
        except Exception as e:
            logger.warning(f"加载词汇库失败: {str(e)}")
    
    # 构建模式库
    pattern_builder = PatternBuilder(vocabulary_data)
    risk_patterns = pattern_builder.build_all_patterns()
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    
    # 保存模式库
    pattern_builder.save_patterns(output)
    
    logger.info(f"构建完成，模式库已保存到: {output}")
    return output

def analyze_conversation(conversation_file, patterns_file, vocabulary_file, output):
    """分析会话风险"""
    logger.info("开始分析会话风险")
    
    # 检查文件是否存在
    for file_path, file_type in [(conversation_file, "会话"), (patterns_file, "模式库"), (vocabulary_file, "词汇库")]:
        if not os.path.exists(file_path):
            logger.error(f"{file_type}文件不存在: {file_path}")
            return None
    
    # 加载会话
    try:
        with open(conversation_file, 'r', encoding='utf-8') as f:
            conversation = json.load(f)
        logger.info(f"已加载会话: {conversation_file}, {len(conversation)} 轮对话")
    except Exception as e:
        logger.error(f"加载会话失败: {str(e)}")
        return None
    
    # 分析会话
    analyzer = ConversationAnalyzer(patterns_file=patterns_file, vocabulary_file=vocabulary_file)
    result = analyzer.analyze_conversation(conversation)
    
    # 保存分析结果
    if output:
        # 确保输出目录存在
        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
        
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=4)
        logger.info(f"分析结果已保存到: {output}")
    
    # 打印摘要
    print("\n===== 会话风险分析摘要 =====")
    print(f"总轮次: {result['conversation_stats']['total_turns']}")
    print(f"风险检测: {'有风险' if result['risk_detected'] else '无风险'}")
    
    if result['risk_detected']:
        print(f"风险类别: {', '.join(result['risk_categories']) if result['risk_categories'] else '无特定类别'}")
        print(f"风险模式: {', '.join(result['risk_patterns']) if result['risk_patterns'] else '无特定模式'}")
        print("\n摘要:")
        print(result['summary'])
    
    return result

if __name__ == "__main__":
    main()