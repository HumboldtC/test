import os
import json
import re  # 添加re模块导入
import logging
from collections import defaultdict
from ..utils.config import ConfigLoader
from .semantic_analyzer import SemanticNetworkAnalyzer
from .multi_role_detector import MultiRolePatternDetector

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RiskDetector:
    """风险检测器，用于检测文本中的风险内容"""
    
    def __init__(self, patterns_file=None, vocabulary_file=None):
        """
        初始化风险检测器
        
        Args:
            patterns_file (str, optional): 风险模式定义文件路径
            vocabulary_file (str, optional): 词汇库文件路径
        """
        # 创建配置加载器
        self.config_loader = ConfigLoader()
        
        # 基本初始化
        self.patterns = {}
        self.pattern_to_category = {}  # 模式ID到大类的映射
        self.pattern_to_name = {}      # 模式ID到名称的映射 
        self.pattern_to_desc = {}      # 模式ID到描述的映射
        self.vocabulary = {}           # 词汇库
        
        # 设置数据目录
        self.data_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.data_dir = os.path.join(self.data_dir, "data")
        os.makedirs(self.data_dir, exist_ok=True)

        # 从配置文件加载风险类别
        risk_categories = self.config_loader.load_config("risk_categories.json")
        self.risk_categories_mapping = {
            "ERC": "显性风险组合类",
            "MCP": "隐喻协作类",
            "IPP": "信息拼图类",
            "TDP": "时序依赖类",
            "REP": "角色特性利用类",
            "CEP": "文化规避类"
        }
        self.risk_categories = risk_categories
        
        # 确保风险类别关键词配置文件存在
        risk_keywords = self.config_loader.load_config("risk_categories_keywords.json")
        if not risk_keywords:
            # 默认风险类别关键词配置将在_detect_risk_categories方法中处理
            pass
    
        # 载入风险类别到文件(如果不存在)
        risk_categories_file = self.config_loader.get_default_config_path("risk_categories.json")
        if not os.path.exists(risk_categories_file):
            self.config_loader.save_config(self.risk_categories, "risk_categories.json")
        
        # 加载风险模式定义
        if patterns_file and os.path.exists(patterns_file):
            try:
                with open(patterns_file, 'r', encoding='utf-8') as f:
                    self.patterns = json.load(f)
                logger.info(f"已加载风险模式定义，包含 {len(self.patterns)} 个大类")
                
                # 构建模式ID到大类的映射
                for category, patterns in self.patterns.items():
                    for pattern in patterns:
                        if "id" in pattern:
                            self.pattern_to_category[pattern["id"]] = category
                            self.pattern_to_name[pattern["id"]] = pattern.get("name", pattern["id"])
                            self.pattern_to_desc[pattern["id"]] = pattern.get("description", "")
            except Exception as e:
                logger.error(f"加载风险模式定义失败: {e}")
                self.patterns = {}
        
        # 加载词汇库
        if vocabulary_file and os.path.exists(vocabulary_file):
            try:
                with open(vocabulary_file, 'r', encoding='utf-8') as f:
                    vocabulary_data = json.load(f)
                    self.vocabulary = vocabulary_data.get('vocabulary', {})
                logger.info(f"已加载词汇库，包含 {len(self.vocabulary)} 个类别")
            except Exception as e:
                logger.error(f"加载词汇库失败: {e}")
                self.vocabulary = {}
    
    # def detect_conversation_risks(self, conversation):
    #     """
    #     检测会话中的风险，包括风险类别和风险模式
    
    #     Args:
    #         conversation (list): 会话列表，格式为 [{"role": "...", "content": "..."}, ...]
    
    #     Returns:
    #         dict: {"risk_categories": [...], "risk_patterns": [...]}
    #     """
    #     logger.info("开始检测会话风险...")

    #     # 提取所有文本内容
    #     texts = []
    #     for turn in conversation:
    #         if isinstance(turn, dict) and "content" in turn:
    #             content = turn.get("content", "").strip()
    #             if content:
    #                 texts.append(content)

    #     # 检测风险类别
    #     risk_categories = self._detect_risk_categories(texts)

    #     # 检测风险模式
    #     risk_patterns, detailed_patterns = self._detect_risk_patterns_with_details(conversation, risk_categories)

    #     # 生成风险摘要
    #     risk_summary = self._generate_risk_summary_with_details(risk_categories, risk_patterns, detailed_patterns)
        
    #     # 判断是否检测到风险
    #     detected = len(risk_categories) > 0 or len(risk_patterns) > 0

    #     return {
    #         "detected": detected,  # 添加 detected 字段
    #         "risk_categories": risk_categories,
    #         "risk_patterns": risk_patterns,
    #         "detailed_patterns": detailed_patterns,
    #         "risk_summary": risk_summary
    #     }

    def _detect_risk_categories(self, texts):
        """
        检测文本中的风险类别 - 增强版本，支持所有wiki_scraper.py中的风险类别
        使用更丰富的口语化、书面语词汇，涵盖各种词性
        
        Args:
            texts (list): 文本列表
            
        Returns:
            list: 检测到的风险类别列表
        """
        # 使用集合存储检测结果，避免重复
        detected_categories = set()
        
        # 从配置文件加载风险类别关键词
        risk_categories_keywords = self.config_loader.load_config("risk_categories_keywords.json")
        
        # 如果配置文件不存在或为空，使用默认关键词并保存到配置文件
        if not risk_categories_keywords:
            logger.info("风险类别关键词配置不存在，使用默认配置并保存")
            exit(0)
        
        # 遍历所有文本，检测风险类别
        for text in texts:
            text = text.strip()
            if not text:
                continue
            
            # 遍历所有风险类别及其关键词
            for category, keywords in risk_categories_keywords.items():
                # 如果已经检测到该类别，则跳过
                if category in detected_categories:
                    continue
                
                # 检测关键词匹配（支持词语拆分和重组）
                for keyword in keywords:
                    # 使用正则表达式检测关键词，支持中英文混合匹配
                    pattern = re.compile(r"\b" + re.escape(keyword) + r"\b", re.IGNORECASE)
                    if pattern.search(text):
                        detected_categories.add(category)
                        logger.info(f"检测到风险类别: {category} (文本: {text})")
                        break  # 跳出关键词循环，继续检测下一个文本
        
        return list(detected_categories)
    
    def _load_risk_patterns(self):
        """
        加载风险模式库
        """
        try:
            patterns_path = os.path.join(self.data_dir, "risk_patterns.json")
            if os.path.exists(patterns_path):
                with open(patterns_path, 'r', encoding='utf-8') as f:
                    self.patterns = json.load(f)
                    
                # 构建模式ID到大类和名称的映射
                self.pattern_to_category = {}
                self.pattern_to_name = {}
                self.pattern_to_desc = {}
                
                for category, patterns_list in self.patterns.items():
                    if isinstance(patterns_list, list):
                        for pattern in patterns_list:
                            if isinstance(pattern, dict) and "id" in pattern:
                                pattern_id = pattern["id"]
                                self.pattern_to_category[pattern_id] = category
                                self.pattern_to_name[pattern_id] = pattern.get("name", pattern_id)
                                self.pattern_to_desc[pattern_id] = pattern.get("description", "")
                
                logger.info(f"成功加载风险模式库，共 {len(self.patterns)} 个大类，"
                          f"{sum(len(patterns_list) if isinstance(patterns_list, list) else 0 for patterns_list in self.patterns.values())} 个模式")
                return True
            else:
                logger.warning(f"风险模式库文件不存在: {patterns_path}")
                self.patterns = {}
                return False
        except Exception as e:
            logger.error(f"加载风险模式库失败: {str(e)}")
            self.patterns = {}
            return False

    def _detect_risk_patterns_with_details(self, conversation, risk_categories):
        """
        检测会话中的风险模式，并提供细粒度风险模式详情
        支持多角色会话场景
        
        Args:
            conversation (list): 会话列表，格式为 [{"role": "...", "content": "..."}, ...]
            risk_categories (list): 风险类别列表
            
        Returns:
            tuple: (风险模式列表, 细粒度风险模式详情字典)
        """
        logger.info("开始检测风险模式...")
        
        detected_patterns = []
        detailed_patterns = defaultdict(list)
        
        # 检查patterns是否为空
        if not self.patterns:
            logger.warning("风险模式库为空，跳过风险模式检测")
            return detected_patterns, detailed_patterns
        
        # 提取所有会话角色
        conversation_roles = set(turn.get("role", "") for turn in conversation 
                           if isinstance(turn, dict) and "role" in turn)
        logger.info(f"检测到会话中的角色: {', '.join(conversation_roles)}")
        
        # 遍历所有风险模式大类
        for pattern_category, pattern_list in self.patterns.items():
            # 确保pattern_list是列表
            if not isinstance(pattern_list, list):
                logger.warning(f"风险模式类别 {pattern_category} 格式错误，应为列表而非 {type(pattern_list)}")
                continue
            
            # 遍历该大类下的所有风险模式
            for pattern_item in pattern_list:
                # 确保pattern_item是字典
                if not isinstance(pattern_item, dict):
                    logger.warning(f"风险模式项格式错误，应为字典而非 {type(pattern_item)}")
                    continue
                
                pattern_id = pattern_item.get("id")
                pattern_name = pattern_item.get("name", pattern_id)
                pattern_keywords = pattern_item.get("keywords", [])
                
                if not pattern_id or not pattern_keywords:
                    continue
                
                # 检查该模式是否已被检测到
                if pattern_id in detected_patterns:
                    continue
            
                # 遍历会话中的每个回合
                for i, turn in enumerate(conversation):
                    # 确保turn是字典
                    if not isinstance(turn, dict):
                        continue
                        
                    role = turn.get("role", "")
                    content = turn.get("content", "").strip()
                    
                    if not content or not role:  # 允许任何角色，不限于user和assistant
                        continue
                    
                    # 检测模式关键词
                    detected = False
                    for keyword in pattern_keywords:
                        if not isinstance(keyword, str):
                            continue
                            
                        if keyword.lower() in content.lower():
                            detected_patterns.append(pattern_id)
                            detailed_patterns[pattern_id].append({
                                "turn": i + 1,
                                "role": role,
                                "content": content,
                                "category": pattern_category,  # 记录大类信息
                                "name": pattern_name  # 记录模式名称
                            })
                            logger.info(f"检测到风险模式: {pattern_id} ({pattern_name}) - 大类: {pattern_category} "
                                      f"(回合 {i+1}, 角色: {role})")
                            detected = True
                            break
                
                    if detected:
                        break  # 如果已经检测到该模式，则跳出回合循环
    
        return detected_patterns, detailed_patterns

    def _generate_risk_summary_with_details(self, risk_categories, risk_patterns, detailed_patterns):
        """
        生成风险摘要，包含风险类别、风险模式及其细节
        支持多角色场景的风险分析
        
        Args:
            risk_categories (list): 风险类别列表
            risk_patterns (list): 风险模式列表
            detailed_patterns (dict): 细粒度风险模式详情字典
            
        Returns:
            str: 风险摘要
        """
        summary = []
        
        # 添加风险类别信息
        if risk_categories:
            summary.append("风险类别: " + ", ".join(risk_categories))

        # 风险模式大类映射
        category_mapping = {
            'ERC': '显性风险组合类',
            'MCP': '隐喻协作类',
            'IPP': '信息拼图类',
            'TDP': '时序依赖类',
            'REP': '角色特性利用类',
            'CEP': '文化规避类'
        }
        
        # 收集所有角色信息
        all_roles = set()
        role_risk_patterns = defaultdict(set)  # 每个角色对应的风险模式
    
        for pattern_id, details in detailed_patterns.items():
            for detail in details:
                role = detail.get('role', '')
                if role:
                    all_roles.add(role)
                    role_risk_patterns[role].add(pattern_id)
    
        # 风险模式信息缓存
        pattern_info = {}
        
        # 构建模式ID到名称和大类的映射
        for pattern_id in risk_patterns:
            # 从detailed_patterns中获取信息
            details = detailed_patterns.get(pattern_id, [])
            if details:
                category = details[0].get("category")
                name = details[0].get("name", pattern_id)
                pattern_info[pattern_id] = {"name": name, "category": category}
            else:
                # 尝试从pattern_id前缀确定大类
                prefix = pattern_id[:3] if len(pattern_id) >= 3 else pattern_id
                category = category_mapping.get(prefix, "未分类")
                
                # 尝试从patterns库中查找详细信息
                found = False
                name = pattern_id
                
                if isinstance(self.patterns, dict):
                    for cat, patterns in self.patterns.items():
                        if isinstance(patterns, list):
                            for pattern in patterns:
                                if isinstance(pattern, dict) and pattern.get("id") == pattern_id:
                                    name = pattern.get("name", pattern_id)
                                    found = True
                                    break
                        if found:
                            break
            
                pattern_info[pattern_id] = {"name": name, "category": category}
    
        # 按大类组织风险模式
        if risk_patterns:
            # 按大类分组模式
            categorized_patterns = {}
            
            for pattern_id in risk_patterns:
                info = pattern_info.get(pattern_id, {"name": pattern_id, "category": "未分类"})
                category = info["category"]
                
                if category not in categorized_patterns:
                    categorized_patterns[category] = []
                
                categorized_patterns[category].append({
                    "id": pattern_id,
                    "name": info["name"]
                })
            
            # 添加按大类分组的风险模式信息
            if categorized_patterns:
                summary.append("\n风险模式分类:")
                
                # 确保大类顺序固定
                category_order = [
                    "显性风险组合类", "隐喻协作类", "信息拼图类", 
                    "时序依赖类", "角色特性利用类", "文化规避类", "未分类"
                ]
                
                # 按固定顺序显示大类
                for category in category_order:
                    if category in categorized_patterns and categorized_patterns[category]:
                        summary.append(f"  {category}:")
                        for pattern in categorized_patterns[category]:
                            pattern_id = pattern["id"]
                            pattern_name = pattern["name"]
                            
                            # 显示模式ID和名称
                            if pattern_id == pattern_name:
                                summary.append(f"    - {pattern_id}")
                            else:
                                summary.append(f"    - {pattern_id}: {pattern_name}")
                
                # 显示其他未在预定义顺序中的大类
                for category in categorized_patterns:
                    if category not in category_order and categorized_patterns[category]:
                        summary.append(f"  {category}:")
                        for pattern in categorized_patterns[category]:
                            pattern_id = pattern["id"]
                            pattern_name = pattern["name"]
                            
                            if pattern_id == pattern_name:
                                summary.append(f"    - {pattern_id}")
                            else:
                                summary.append(f"    - {pattern_id}: {pattern_name}")
        
        # 添加按角色分组的风险分析
        if all_roles:
            summary.append("\n按角色的风险分析:")
            for role in sorted(all_roles):
                pattern_ids = role_risk_patterns[role]
                if pattern_ids:
                    summary.append(f"  角色 \"{role}\" 相关风险模式:")
                    for pattern_id in pattern_ids:
                        info = pattern_info.get(pattern_id, {"name": pattern_id, "category": "未分类"})
                        name = info["name"]
                        category = info["category"]
                        
                        if pattern_id == name:
                            summary.append(f"    - {pattern_id} (大类: {category})")
                        else:
                            summary.append(f"    - {pattern_id}: {name} (大类: {category})")
        
        # 添加详细风险模式信息
        summary.append("\n风险模式详情:")
        for pattern_id in risk_patterns:
            info = pattern_info.get(pattern_id, {"name": pattern_id, "category": "未分类"})
            name = info["name"]
            category = info["category"]
            
            # 显示模式ID、名称和所属大类
            if pattern_id == name:
                summary.append(f"  {pattern_id} (大类: {category}):")
            else:
                summary.append(f"  {pattern_id}: {name} (大类: {category}):")
            
            # 显示细节
            details = detailed_patterns.get(pattern_id, [])
            for detail in details:
                summary.append(f"    - 回合 {detail.get('turn')}, 角色: {detail.get('role')}")
                content = detail.get('content', '')
                # 截断过长内容
                content_preview = content[:100] + "..." if len(content) > 100 else content
                summary.append(f"      内容: {content_preview}")
    
        return "\n".join(summary)

    def detect_risks(self, conversation):
        """
        检测会话中的风险
        
        Args:
            conversation (list): 会话列表，格式为 [{"role": "...", "content": "..."}, ...]
            
        Returns:
            dict: 风险检测结果，包含风险类别、风险模式和风险分数
        """
        # 加载风险模式库
        self._load_patterns()
        
        # 提取对话文本
        texts = []
        for turn in conversation:
            if isinstance(turn, dict) and "content" in turn and turn.get("role") in ["user", "assistant"]:
                texts.append(turn["content"])
        
        # 检测风险类别
        risk_categories = self._detect_risk_categories(texts)
        
        # 检测风险模式
        risk_patterns, detailed_patterns = self._detect_risk_patterns_with_details(conversation, risk_categories)
        
        # 计算风险分数
        risk_score = self._calculate_risk_score(risk_categories, risk_patterns)
        
        # 生成风险摘要
        risk_summary = self._generate_risk_summary_with_details(risk_categories, risk_patterns, detailed_patterns)
        
        return {
            "risk_categories": risk_categories,
            "risk_patterns": risk_patterns,
            "risk_score": risk_score,
            "risk_summary": risk_summary,
            "detailed_patterns": detailed_patterns
        }


    def detect_conversation_risks(self, conversation):
        """
        检测会话中的风险，包括风险类别和风险模式
        增强版：支持多角色会话和分散式危险信息检测
        
        Args:
            conversation (list): 会话列表，格式为 [{"role": "...", "content": "..."}, ...]
        
        Returns:
            dict: 风险检测结果
        """
        logger.info("开始检测会话风险...")

        # 提取所有文本内容
        texts = []
        for turn in conversation:
            if isinstance(turn, dict) and "content" in turn:
                content = turn.get("content", "").strip()
                if content:
                    texts.append(content)

        # 检测风险类别
        risk_categories = self._detect_risk_categories(texts)

        # 检测风险模式
        risk_patterns, detailed_patterns = self._detect_risk_patterns_with_details(conversation, risk_categories)

        # 检测分散式风险内容（新增）
        semantic_risks = self._detect_semantic_risks(conversation)
        
        # 检测多角色风险模式（新增）
        multi_role_risks = self._detect_multi_role_risks(conversation)

        # 合并风险检测结果
        detected = (
            len(risk_categories) > 0 
            or len(risk_patterns) > 0 
            or semantic_risks.get("detected", False)
            or multi_role_risks.get("multi_role_risk_detected", False)
        )
        
        # 合并风险模式
        combined_risk_patterns = risk_patterns.copy()
        if multi_role_risks.get("risk_patterns"):
            for pattern in multi_role_risks["risk_patterns"]:
                pattern_id = pattern["pattern_id"]
                if pattern_id not in combined_risk_patterns:
                    combined_risk_patterns.append(pattern_id)
        
        # 生成风险摘要（包含多角色和分散式风险）
        risk_summary = self._generate_enhanced_risk_summary(
            risk_categories, 
            combined_risk_patterns, 
            detailed_patterns,
            semantic_risks,
            multi_role_risks
        )

        return {
            "detected": detected,
            "risk_categories": risk_categories,
            "risk_patterns": combined_risk_patterns,
            "detailed_patterns": detailed_patterns,
            "risk_summary": risk_summary,
            "semantic_risks": semantic_risks,
            "multi_role_risks": multi_role_risks
        }

    def _detect_semantic_risks(self, conversation):
        """检测语义网络风险模式"""
        try:
            from .semantic_analyzer import SemanticNetworkAnalyzer
            
            # 创建语义网络分析器实例
            analyzer = SemanticNetworkAnalyzer(risk_vocabulary=self.vocabulary)
            
            # 构建语义网络
            semantic_graph = analyzer.build_semantic_network(conversation)
            
            # 检测风险知识流图
            risk_findings = analyzer.detect_dangerous_knowledge_flow()
            
            return risk_findings
            
        except Exception as e:
            logger.error(f"语义网络风险分析失败: {e}")
            import traceback
            traceback.print_exc()
            return {"detected": False, "error": str(e)}

    def _detect_multi_role_risks(self, conversation):
        """检测多角色互动风险模式"""
        try:
            from .multi_role_detector import MultiRolePatternDetector
            
            # 创建多角色风险检测器实例
            detector = MultiRolePatternDetector(risk_detector=self)
            
            # 检测多角色风险
            multi_role_risks = detector.detect_multi_role_risks(conversation)
            
            return multi_role_risks
            
        except Exception as e:
            logger.error(f"多角色风险分析失败: {e}")
            import traceback
            traceback.print_exc()
            return {"multi_role_risk_detected": False, "risk_score": 0, "error": str(e)}

    def _generate_enhanced_risk_summary(self, risk_categories, risk_patterns, detailed_patterns, 
                                   semantic_risks, multi_role_risks):
        """
        生成增强的风险摘要，包括多角色和分散式风险 - 泛化版
        
        Args:
            risk_categories (list): 风险类别列表
            risk_patterns (list): 风险模式列表
            detailed_patterns (dict): 细粒度风险模式详情
            semantic_risks (dict): 语义风险分析结果
            multi_role_risks (dict): 多角色风险分析结果
            
        Returns:
            str: 风险摘要
        """
        summary_parts = []
        
        # 基本风险类别和模式摘要
        if risk_categories:
            categories_str = "、".join(risk_categories)
            summary_parts.append(f"检测到以下风险类别：{categories_str}。")
    
        # 风险模式分类摘要 - 支持更多模式类型
        if risk_patterns:
            # 统计各类模式数量
            pattern_counts = {}
            for pattern_id in risk_patterns:
                prefix = pattern_id[:3]
                pattern_counts[prefix] = pattern_counts.get(prefix, 0) + 1
        
            # 风险模式类型映射
            pattern_type_names = {
                "ERC": "显性风险组合类",
                "MCP": "隐喻协作类",
                "IPP": "信息拼图类",
                "TDP": "时序依赖类",
                "REP": "角色特性利用类",
                "CEP": "文化规避类",
                "DRP": "分散式风险类"
            }
        
            # 生成风险模式统计描述
            risk_pattern_stats = []
            for prefix, count in pattern_counts.items():
                if prefix in pattern_type_names:
                    risk_pattern_stats.append(f"{pattern_type_names[prefix]}({count})")
                else:
                    risk_pattern_stats.append(f"{prefix}类({count})")
        
            if risk_pattern_stats:
                patterns_str = "、".join(risk_pattern_stats)
                summary_parts.append(f"发现的风险模式类型包括：{patterns_str}。")
    
        # 语义风险摘要 - 扩展为更通用的描述
        if semantic_risks.get("detected", False):
            summary_parts.append("\n【语义网络风险分析】")
            
            # 添加语义风险概述
            risk_level = semantic_risks.get("risk_level", "none").upper()
            risk_score = semantic_risks.get("overall_risk_score", 0)
            summary_parts.append(f"语义风险等级: {risk_level}，风险分数: {risk_score:.2f}")
            
            # 添加危险组合信息
            dangerous_combos = semantic_risks.get("dangerous_combinations", [])
            if dangerous_combos:
                summary_parts.append("检测到以下危险概念组合:")
                
                # 按类别分组组织危险组合
                category_combos = defaultdict(list)
                for combo in dangerous_combos:
                    category = combo.get("category", "未分类")
                    category_combos[category].append(combo)
                
                # 显示各类别下的危险组合
                for category, combos in category_combos.items():
                    # 只显示前3个组合
                    display_combos = combos[:3]
                    concepts_list = [", ".join(c.get("concepts", [])) for c in display_combos]
                    
                    summary_parts.append(f"  - {category}: {'; '.join(concepts_list)}")
                    
                    # 如果还有更多组合，显示剩余数量
                    if len(combos) > 3:
                        summary_parts.append(f"    以及{len(combos)-3}个其他{category}组合")
            
            # 添加角色风险信息
            role_risks = semantic_risks.get("role_based_risks", {})
            if role_risks:
                pattern = role_risks.get("pattern")
                description = role_risks.get("description")
                if pattern and description:
                    summary_parts.append(f"角色风险模式: {pattern} - {description}")
                    
                    # 添加各角色贡献的信息
                    role_contributions = role_risks.get("role_contributions", {})
                    if role_contributions:
                        summary_parts.append("各角色贡献的危险概念:")
                        for role, concepts in role_contributions.items():
                            concepts_str = ", ".join(concepts[:5])
                            if len(concepts) > 5:
                                concepts_str += f" 等{len(concepts)}个概念"
                            summary_parts.append(f"    - {role}: {concepts_str}")
    
        # 多角色风险摘要 - 增强泛化性描述
        if multi_role_risks.get("multi_role_risk_detected", False):
            summary_parts.append("\n【多角色风险分析】")
            risk_level = multi_role_risks.get("risk_level", "low")
            risk_score = multi_role_risks.get("risk_score", 0)
            summary_parts.append(f"多角色风险等级: {risk_level.upper()}，风险分数: {risk_score:.2f}")
            
            # 添加多角色风险模式信息
            risk_patterns = multi_role_risks.get("risk_patterns", [])
            if risk_patterns:
                # 按类型分组风险模式
                pattern_types = defaultdict(list)
                for pattern in risk_patterns:
                    pattern_type = pattern.get("pattern_type", "未知")
                    pattern_types[pattern_type].append(pattern)
                
                summary_parts.append("检测到以下多角色风险模式类型:")
                
                # 风险模式类型映射到中文描述
                type_descriptions = {
                    "information_puzzle": "信息拼图风险",
                    "role_interaction": "角色交互风险",
                    "role_sensitivity": "角色敏感性风险",
                    "topic_shift": "话题突然转移风险",
                    "complementary_information": "互补信息风险",
                    "sensitive_topic": "敏感主题风险"
                }
                
                # 显示各类型的风险模式
                for pattern_type, patterns in pattern_types.items():
                    type_desc = type_descriptions.get(pattern_type, pattern_type)
                    count = len(patterns)
                    
                    # 选择最高风险分数的模式作为代表
                    highest_risk = max(patterns, key=lambda p: p.get("risk_score", 0))
                    highest_desc = highest_risk.get("description", "")
                    highest_score = highest_risk.get("risk_score", 0)
                    
                    summary_parts.append(f"  - {type_desc} ({count}个): 最高风险 {highest_score:.2f} - {highest_desc}")
            
            # 添加风险因素详情
            risk_factors = multi_role_risks.get("risk_factors", [])
            if risk_factors:
                high_factors = [f for f in risk_factors if f["score"] >= 0.5]
                if high_factors:
                    factor_descs = []
                    for factor in high_factors:
                        factor_descs.append(f"{factor['type']}({factor['score']:.2f})")
                    summary_parts.append(f"主要风险因素: {', '.join(factor_descs)}")
            
            # 添加信息拼图风险详情
            info_puzzle = multi_role_risks.get("details", {}).get("information_puzzle", {})
            if info_puzzle.get("risk_detected", False):
                risk_domains = info_puzzle.get("risk_domains", [])
                if risk_domains:
                    domains_str = ", ".join([f"{domain['domain']}({domain['risk_score']:.2f})" 
                                          for domain in risk_domains])
                    summary_parts.append(f"跨角色信息拼图涉及的危险领域: {domains_str}")
            
            # 添加补充风险因素 - 增强泛化性
            complementary_info = multi_role_risks.get("details", {}).get("complementary_info_risk", {})
            if complementary_info.get("risk_detected", False):
                summary_parts.append("检测到角色间互补信息风险，多个角色共同构建完整风险知识。")
            
            topic_shift = multi_role_risks.get("details", {}).get("topic_shift_risk", {})
            if topic_shift.get("risk_detected", False):
                shifts_count = len(topic_shift.get("shifts", []))
                summary_parts.append(f"检测到{shifts_count}处可疑的话题突然转移模式，可能是分散式风险传递。")
    
        # 综合风险判断（整合所有风险来源）
        has_risks = (
            len(risk_categories) > 0 
            or len(risk_patterns) > 0 
            or semantic_risks.get("detected", False)
            or multi_role_risks.get("multi_role_risk_detected", False)
        )
        
        if not has_risks:
            return "未检测到明显风险内容。"
        
        # 特别强调分散式风险内容
        if semantic_risks.get("detected", False) or multi_role_risks.get("multi_role_risk_detected", False):
            if not risk_categories and not risk_patterns:
                summary_parts.insert(0, "⚠️ 警告：检测到分散式风险内容！常规检测未发现明显风险，但跨角色和语义分析显示存在信息拼图风险。")
        
        return "\n".join(summary_parts)