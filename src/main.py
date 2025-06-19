import argparse
import json
import os
import logging
import sys

# 修复导入路径问题
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from src.scraper.wiki_scraper import WikiScraper
from src.risk_analyzer.pattern_builder import PatternBuilder
from src.risk_analyzer.risk_detector import RiskDetector
from src.risk_analyzer.conversation_analyzer import ConversationAnalyzer
from src.data.data_manager import DataManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """内容风险分析工具主函数"""
    parser = argparse.ArgumentParser(description="维基百科内容风险分析工具")
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
    
    else:
        parser.print_help()

def scrape_wiki(topics, lang, output):
    """爬取维基百科内容"""
    logger.info(f"开始处理主题: {', '.join(topics)}, 语言: {lang}")
    
    # 创建WikiScraper实例
    wiki_dir = os.path.join("data", "wikidump")
    os.makedirs(wiki_dir, exist_ok=True)
    scraper = WikiScraper(data_dir=wiki_dir)
    
    # 处理主题
    result = scraper.batch_scrape(topics, lang)
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    
    # 保存结果
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
    
    logger.info(f"处理完成，结果已保存到: {output}")
    logger.info(f"找到 {len(result['vocabulary'])} 个风险类别")
    
    # 打印发现的风险类别
    if result['vocabulary']:
        print("\n发现的风险类别:")
        for category in result['vocabulary']:
            print(f"- {category}")
    else:
        print("\n未发现任何风险类别")
    
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
    
    # 统计模式数量
    total_patterns = sum(len(patterns) for patterns in risk_patterns.values())
    logger.info(f"构建完成，共生成 {total_patterns} 个风险模式，已保存到: {output}")
    return output

def analyze_conversation(conversation_file, patterns_file, vocabulary_file, output=None):
    """分析会话风险"""
    logger.info("开始分析会话风险")
    
    # 检查文件是否存在
    for file_path, file_type in [(conversation_file, "会话"), (patterns_file, "模式库"), (vocabulary_file, "词汇库")]:
        if file_path and not os.path.exists(file_path):
            logger.error(f"{file_type}文件不存在: {file_path}")
            return None
    
    # 创建目录（如果需要）
    if output:
        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    
    # 加载会话
    try:
        with open(conversation_file, 'r', encoding='utf-8') as f:
            conversation = json.load(f)
        logger.info(f"已加载会话: {conversation_file}, {len(conversation)} 轮对话")
    except Exception as e:
        logger.error(f"加载会话失败: {str(e)}")
        return None
    
    # 创建风险检测器和分析器
    try:
        risk_detector = RiskDetector(patterns_file=patterns_file, vocabulary_file=vocabulary_file)
        analyzer = ConversationAnalyzer(risk_detector=risk_detector)
        result = analyzer.analyze_conversation(conversation)
    except Exception as e:
        logger.error(f"分析会话时发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    
    # 保存分析结果
    if output:
        try:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
            logger.info(f"分析结果已保存到: {output}")
        except Exception as e:
            logger.error(f"保存分析结果失败: {str(e)}")
    
    # 打印摘要
    print("\n===== 会话风险分析摘要 =====")
    print(f"总轮次: {result['conversation_stats']['total_turns']}")
    print(f"风险检测: {'有风险' if result['risk_detected'] else '无风险'}")
    
    if result['risk_detected']:
        print(f"风险评分: {result['risk_score']}/100")
        
        # 打印风险类别
        if result['risk_categories']:
            print(f"风险类别: {', '.join(result['risk_categories'])}")
        
        # 显示多角色信息
        roles = set()
        for turn in conversation:
            if isinstance(turn, dict) and "role" in turn:
                role = turn.get("role")
                if role:
                    roles.add(role)
        
        print(f"\n检测到 {len(roles)} 个角色: {', '.join(roles)}")
        
        # 打印风险模式（按大类组织，并显示小类名称）
        if result['risk_patterns']:
            # 从风险检测器获取模式映射信息
            pattern_to_category = risk_detector.pattern_to_category
            pattern_to_name = risk_detector.pattern_to_name
            
            # 按大类组织风险模式
            categorized_patterns = {}
            for pattern_id in result['risk_patterns']:
                category = pattern_to_category.get(pattern_id, "未分类")
                pattern_name = pattern_to_name.get(pattern_id, pattern_id)
                
                if category not in categorized_patterns:
                    categorized_patterns[category] = []
                
                categorized_patterns[category].append((pattern_id, pattern_name))
            
            # 打印按大类组织的风险模式
            print("\n风险模式分类:")
            for category, patterns in categorized_patterns.items():
                print(f"  {category}:")
                for pattern_id, pattern_name in patterns:
                    if pattern_id == pattern_name:
                        print(f"    - {pattern_id}")
                    else:
                        print(f"    - {pattern_id}: {pattern_name}")
        
        # 打印多角色风险结果（新增）
        multi_role_risks = result.get('multi_role_risks', {})
        if multi_role_risks.get('multi_role_risk_detected', False):
            print("\n多角色风险分析结果:")
            print(f"  风险等级: {multi_role_risks.get('risk_level', '未知').upper()}")
            print(f"  风险分数: {multi_role_risks.get('risk_score', 0)}")
            
            # 打印角色风险贡献
            risk_patterns = multi_role_risks.get('risk_patterns', [])
            if risk_patterns:
                print("  检测到的多角色风险模式:")
                for i, pattern in enumerate(risk_patterns):
                    print(f"    - {pattern.get('pattern_id', '未知')}: {pattern.get('description', '未知')}")
                    roles = pattern.get('roles_involved', [])
                    if roles:
                        print(f"      涉及角色: {', '.join(roles)}")
        
        # 打印语义网络风险结果（新增）
        semantic_risks = result.get('semantic_risks', {})
        if semantic_risks.get('detected', False):
            print("\n语义网络风险分析结果:")
            print(f"  风险等级: {semantic_risks.get('risk_level', '未知').upper()}")
            print(f"  风险分数: {semantic_risks.get('overall_risk_score', 0)}")
            
            # 打印危险组合
            dangerous_combos = semantic_risks.get('dangerous_combinations', [])
            if dangerous_combos:
                print("  检测到的危险概念组合:")
                for combo in dangerous_combos[:5]:  # 限制显示数量
                    concepts = ", ".join(combo.get('concepts', []))
                    category = combo.get('category', '未知')
                    print(f"    - {category}: {concepts}")
        
        print("\n摘要:")
        print(result['summary'])
    
    return result
    

if __name__ == "__main__":
    main()