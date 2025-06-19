import json
import logging
from collections import Counter
from .risk_detector import RiskDetector

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ConversationAnalyzer:
    """会话风险分析器"""
    
    def __init__(self, risk_detector=None, patterns_file=None, vocabulary_file=None):
        """
        初始化会话风险分析器
        
        Args:
            risk_detector (RiskDetector, optional): 风险检测器实例
            patterns_file (str, optional): 风险模式库文件路径
            vocabulary_file (str, optional): 风险词汇库文件路径
        """
        if risk_detector:
            self.risk_detector = risk_detector
        else:
            self.risk_detector = RiskDetector(patterns_file, vocabulary_file)
            
        logger.info("会话风险分析器初始化完成")
    
    def analyze_conversation(self, conversation):
        """
        分析会话风险 - 增强版，支持分散式风险和多角色场景
        
        Args:
            conversation (list): 会话列表，格式为 [{"role": "...", "content": "..."}, ...]
            
        Returns:
            dict: 分析结果
        """
        # 检查会话格式
        if not isinstance(conversation, list):
            logger.error("会话必须是列表格式")
            return {"error": "会话格式错误，必须是列表"}
        
        if not conversation:
            logger.error("会话列表为空")
            return {"error": "会话列表为空"}
        
        # 会话统计信息
        conversation_stats = self._get_conversation_stats(conversation)
        
        # 风险检测 - 使用增强的风险检测功能
        risk_result = self.risk_detector.detect_conversation_risks(conversation)
        
        # 风险评分（0-100）- 综合考虑多角色和分散式风险
        risk_score = self._calculate_enhanced_risk_score(conversation, risk_result)
        
        # 检查是否有新增的风险检测结果
        has_semantic_risks = risk_result.get("semantic_risks", {}).get("detected", False)
        has_multi_role_risks = risk_result.get("multi_role_risks", {}).get("multi_role_risk_detected", False)
        
        # 风险检测 - 综合传统和增强检测结果
        risk_detected = risk_result["detected"]
        
        # 整合分析结果
        result = {
            "conversation_stats": conversation_stats,
            "risk_detected": risk_detected,
            "risk_score": risk_score,
            "risk_categories": risk_result.get("risk_categories", []),
            "risk_patterns": risk_result.get("risk_patterns", []),
            "summary": risk_result.get("risk_summary", ""),
            "semantic_risks": risk_result.get("semantic_risks", {}),
            "multi_role_risks": risk_result.get("multi_role_risks", {})
        }
        
        logger.info(f"会话分析完成，风险检测结果: {'有风险' if result['risk_detected'] else '无风险'}")
        
        return result

    def _calculate_enhanced_risk_score(self, conversation, risk_result):
        """
        计算增强的风险评分，考虑多角色和分散式风险
        
        Args:
            conversation (list): 会话列表
            risk_result (dict): 风险检测结果
            
        Returns:
            int: 风险评分(0-100)
        """
        # 基础分数
        base_score = 0
        
        # 检测到的风险类别加分
        category_score = len(risk_result.get("risk_categories", [])) * 15
        
        # 检测到的风险模式加分
        pattern_score = len(risk_result.get("risk_patterns", [])) * 20
        
        # 语义网络风险加分 (新增)
        semantic_risks = risk_result.get("semantic_risks", {})
        semantic_score = 0
        if semantic_risks.get("detected", False):
            semantic_base = 30  # 发现语义网络风险的基础分
            risk_level_score = {
                "critical": 40,
                "high": 30,
                "medium": 20,
                "low": 10
            }
            level = semantic_risks.get("risk_level", "low")
            semantic_score = risk_level_score.get(level, 0)
        
        # 多角色风险加分 (新增)
        multi_role_risks = risk_result.get("multi_role_risks", {})
        multi_role_score = 0
        if multi_role_risks.get("multi_role_risk_detected", False):
            multi_role_base = 25  # 发现多角色风险的基础分
            role_risk_score = int(multi_role_risks.get("risk_score", 0) * 50)  # 将0-1的分数转换为0-50分
            multi_role_score = multi_role_base + role_risk_score
        
        # 综合风险评分
        risk_score = base_score + category_score + pattern_score
        
        # 如果常规检测没有发现风险，但发现了语义或多角色风险，使用这些风险分数
        if risk_score == 0 and (semantic_score > 0 or multi_role_score > 0):
            risk_score = max(semantic_score, multi_role_score)
        else:
            # 否则将这些分数作为补充
            additional_score = max(semantic_score, multi_role_score) * 0.7  # 70%权重
            risk_score += additional_score
        
        # 上限100分
        risk_score = min(100, risk_score)
        
        return int(risk_score)
    
    def _get_conversation_stats(self, conversation):
        """
        获取会话统计信息
        
        Args:
            conversation (list): 会话列表
            
        Returns:
            dict: 会话统计信息
        """
        # 计算会话轮数
        total_turns = len(conversation)
        
        # 统计用户和助手消息数量
        user_turns = sum(1 for turn in conversation if turn.get("role") == "user")
        assistant_turns = sum(1 for turn in conversation if turn.get("role") == "assistant")
        
        # 计算平均消息长度
        user_msg_lengths = [len(turn.get("content", "")) for turn in conversation if turn.get("role") == "user"]
        assistant_msg_lengths = [len(turn.get("content", "")) for turn in conversation if turn.get("role") == "assistant"]
        
        avg_user_msg_length = sum(user_msg_lengths) / len(user_msg_lengths) if user_msg_lengths else 0
        avg_assistant_msg_length = sum(assistant_msg_lengths) / len(assistant_msg_lengths) if assistant_msg_lengths else 0
        
        # 返回统计信息
        return {
            "total_turns": total_turns,
            "user_turns": user_turns,
            "assistant_turns": assistant_turns,
            "avg_user_msg_length": round(avg_user_msg_length, 2),
            "avg_assistant_msg_length": round(avg_assistant_msg_length, 2)
        }
    
    def _calculate_risk_score(self, conversation, risk_result):
        """
        计算风险评分
        
        Args:
            conversation (list): 会话列表
            risk_result (dict): 风险检测结果
            
        Returns:
            int: 风险评分(0-100)
        """
        # 基础分数
        base_score = 0
        
        # 检测到的风险类别加分
        category_score = len(risk_result.get("risk_categories", [])) * 15
        
        # 检测到的风险模式加分
        pattern_score = len(risk_result.get("risk_patterns", [])) * 20
        
        # 风险评分 = 基础分数 + 类别分数 + 模式分数，上限100分
        risk_score = base_score + category_score + pattern_score
        risk_score = min(100, risk_score)
        
        return risk_score
    
    def _generate_risk_summary(self, conversation, risk_result):
        """
        生成风险摘要
        
        Args:
            conversation (list): 会话列表
            risk_result (dict): 风险检测结果
            
        Returns:
            str: 风险摘要
        """
        # 检查是否有 detected 键，如果没有，则基于风险类别和模式判断
        has_risks = risk_result.get("detected", False)
        
        # 如果没有 detected 键，则基于风险类别和模式判断
        if "detected" not in risk_result:
            has_risks = len(risk_result.get("risk_categories", [])) > 0 or len(risk_result.get("risk_patterns", [])) > 0
        
        if not has_risks:
            return "未检测到明显风险内容。"
        
        summary_parts = []
        
        # 添加风险类别摘要
        if risk_result.get("risk_categories"):
            categories_str = "、".join(risk_result["risk_categories"])
            summary_parts.append(f"检测到以下风险类别：{categories_str}。")
        
        # 添加风险模式摘要
        if risk_result.get("risk_patterns"):
            patterns = risk_result["risk_patterns"]
            
            # 按模式类型分组
            explicit_patterns = [p for p in patterns if p.startswith("P1")]
            metaphorical_patterns = [p for p in patterns if p.startswith("P2")]
            information_patterns = [p for p in patterns if p.startswith("P3")]
            temporal_patterns = [p for p in patterns if p.startswith("P4")]
            role_patterns = [p for p in patterns if p.startswith("P5")]
            cultural_patterns = [p for p in patterns if p.startswith("P6")]
            
            # 生成分类摘要
            if explicit_patterns:
                summary_parts.append("存在显性风险组合，多种风险内容在会话中共同出现。")
            
            if metaphorical_patterns:
                summary_parts.append("检测到隐喻协作风险，通过比喻或类比方式掩盖风险内容。")
            
            if information_patterns:
                summary_parts.append("存在信息拼图风险，多轮对话中收集了敏感信息。")
            
            if temporal_patterns:
                summary_parts.append("发现时序依赖风险，随对话进行风险程度逐渐提升。")
            
            if role_patterns:
                summary_parts.append("检测到角色特性利用，通过角色扮演或假冒权威传递风险内容。")
            
            if cultural_patterns:
                summary_parts.append("存在文化规避风险，利用语言或文化差异规避风险检测。")
        
        # 生成具体风险摘要
        specific_risks = []
        
        if "个人隐私" in risk_result.get("risk_categories", []):
            specific_risks.append("涉及个人隐私信息收集或泄露。")
        
        if "恶意代码生成" in risk_result.get("risk_categories", []):
            specific_risks.append("存在恶意代码生成或使用风险。")
        
        if "非法活动" in risk_result.get("risk_categories", []):
            specific_risks.append("涉及非法活动内容。")
        
        if "欺诈活动" in risk_result.get("risk_categories", []):
            specific_risks.append("存在欺诈或诈骗风险。")
        
        if specific_risks:
            summary_parts.append("具体风险包括：" + " ".join(specific_risks))
        
        # 合并摘要
        summary = " ".join(summary_parts)
        
        return summary
    
    def save_analysis_result(self, result, output_file):
        """将分析结果保存到文件"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
            logger.info(f"分析结果已保存到: {output_file}")
            return True
        except Exception as e:
            logger.error(f"保存分析结果失败: {str(e)}")
            return False
    
    def analyze_conversation_file(self, conversation_file, output_file=None):
        """
        分析会话文件中的风险
        
        Args:
            conversation_file (str): 会话文件路径，JSON格式
            output_file (str, optional): 输出文件路径
            
        Returns:
            dict: 分析结果
        """
        try:
            with open(conversation_file, 'r', encoding='utf-8') as f:
                conversation = json.load(f)
                
            result = self.analyze_conversation(conversation)
            
            if output_file:
                self.save_analysis_result(result, output_file)
                
            return result
        except Exception as e:
            logger.error(f"分析会话文件失败: {str(e)}")
            raise