# -*- coding: utf-8 -*-
import logging
import os
import networkx as nx
from collections import defaultdict, Counter
from ..utils.config import ConfigLoader

logger = logging.getLogger(__name__)

class MultiRolePatternDetector:
    """多角色会话风险模式检测器，专门针对跨角色的信息拼图风险"""
    
    def __init__(self, risk_detector=None):
        """初始化多角色模式检测器"""
        self.risk_detector = risk_detector
        
        # 创建配置加载器
        self.config_loader = ConfigLoader()
        
        # 从配置文件加载域关键词
        domains_config = self.config_loader.load_config("domains.json")
        self.domain_keywords = domains_config.get("domain_keywords", {})
        self.sensitive_topics = domains_config.get("sensitive_topics", {})
        
        # 从配置文件加载角色定义
        roles_config = self.config_loader.load_config("roles.json")
        self.role_specific_contributions = roles_config.get("role_specific_contributions", {})
        
        # 加载角色交互风险 - 配置文件中以字符串键存储，需要转换回元组
        role_interaction_risk_config = roles_config.get("role_interaction_risk", {})
        self.role_interaction_risk = {}
        for key_str, value in role_interaction_risk_config.items():
            # 将字符串键"role1,role2"转换为元组(role1, role2)
            roles = key_str.split(",")
            if len(roles) == 2:
                self.role_interaction_risk[(roles[0], roles[1])] = value
        
        # 将配置保存到默认文件(如果不存在)
        self._save_default_configs_if_not_exist()
        
    def _save_default_configs_if_not_exist(self):
        """如果配置文件不存在，则保存默认配置"""
        domains_file = self.config_loader.get_default_config_path("domains.json")
        if not os.path.exists(domains_file):
            domains_config = {
                "domain_keywords": self.domain_keywords,
                "sensitive_topics": self.sensitive_topics
            }
            self.config_loader.save_config(domains_config, "domains.json")
        
        roles_file = self.config_loader.get_default_config_path("roles.json")
        if not os.path.exists(roles_file):
            # 将元组键转换为字符串键
            role_interaction_risk_str = {}
            for (role1, role2), value in self.role_interaction_risk.items():
                role_interaction_risk_str[f"{role1},{role2}"] = value
            
            roles_config = {
                "role_specific_contributions": self.role_specific_contributions,
                "role_interaction_risk": role_interaction_risk_str
            }
            self.config_loader.save_config(roles_config, "roles.json")
    
    def detect_multi_role_risks(self, conversation):
        """
        检测多角色会话中的风险模式 - 增强泛化版本
        
        Args:
            conversation (list): 会话列表，格式为 [{"role": "...", "content": "..."}, ...]
            
        Returns:
            dict: 风险检测结果
        """
        # 提取所有角色
        roles = self._extract_roles(conversation)
        logger.info(f"检测到会话中的角色: {', '.join(roles)}")
        
        # 角色数量检查 - 降低阈值以提高泛化性
        if len(roles) < 2:  # 从3降为2，增强泛化性
            logger.info(f"角色数量({len(roles)})小于2，不符合多角色信息拼图风险模式")
            return {
                "multi_role_risk_detected": False,
                "risk_score": 0,
                "risk_patterns": [],
                "details": "角色数量不足，不符合多角色拼图风险特征"
            }
        
        # 提取对话主题
        all_texts = " ".join([turn.get("content", "") for turn in conversation if isinstance(turn, dict) and "content" in turn])
        
        # 会话整体风险评估 - 检查是否包含敏感主题，不局限于特定领域
        overall_domain_risk = self._assess_overall_domain_risk(all_texts)
        
        # 构建角色-主题映射
        role_topics = self._map_roles_to_topics(conversation)
        
        # 检测危险信息拼图
        info_puzzle = self._detect_information_puzzle(role_topics)
        
        # 角色交互序列分析
        interaction_risk = self._analyze_role_interaction_sequence(conversation)
        
        # 角色身份敏感性评估
        role_sensitivity = self._evaluate_role_sensitivity(roles)
        
        # 话题转移检测 - 新增功能
        topic_shift_risk = self._detect_topic_shifts(conversation)
        
        # 信息补充模式检测 - 新增功能
        complementary_info_risk = self._detect_complementary_information(conversation)
        
        # 综合风险评估 - 整合更多风险因素
        overall_risk = self._calculate_enhanced_overall_risk(
            info_puzzle, 
            interaction_risk, 
            role_sensitivity, 
            topic_shift_risk, 
            complementary_info_risk,
            overall_domain_risk
        )
        
        return overall_risk

    def _assess_overall_domain_risk(self, text):
        """评估会话整体涉及的敏感度，不局限于特定领域"""
        # 更全面的敏感主题关键词
        sensitive_topics = {
            "暴力": ["暴力", "攻击", "伤害", "杀害", "殴打", "斗殴", "伤害", "武力"],
            "毒品": ["毒品", "吸毒", "贩毒", "成瘾", "戒毒", "戒断", "药物滥用"],
            "色情": ["色情", "露骨", "性行为", "性内容", "情色", "成人内容"],
            "歧视": ["歧视", "种族", "性别", "仇恨", "偏见", "刻板印象", "冒犯"],
            "极端主义": ["极端", "激进", "恐怖", "极化", "偏激", "煽动", "暴乱"],
            "欺诈": ["欺诈", "诈骗", "骗局", "假冒", "盗用", "非法", "违法"],
            "自杀": ["自杀", "自残", "伤害自己", "轻生", "结束生命", "死亡"],
            "虐待": ["虐待", "侵犯", "骚扰", "霸凌", "威胁", "恐吓", "强迫"]
        }
        
        # 评估文本中敏感主题的出现情况
        lower_text = text.lower()
        topic_scores = {}
        
        for topic, keywords in sensitive_topics.items():
            matches = sum(1 for keyword in keywords if keyword.lower() in lower_text)
            if matches > 0:
                # 计算主题风险分数，与匹配词数量相关
                score = min(1.0, matches / len(keywords) * 1.5)
                topic_scores[topic] = round(score, 2)
        
        # 计算整体风险分数
        if not topic_scores:
            return {
                "risk_detected": False,
                "risk_score": 0,
                "sensitive_topics": []
            }
        
        max_score = max(topic_scores.values())
        sensitive_topics_found = [{"topic": topic, "score": score} 
                                 for topic, score in topic_scores.items()]
        
        return {
            "risk_detected": max_score > 0.3,  # 风险阈值
            "risk_score": round(max_score, 2),
            "sensitive_topics": sensitive_topics_found
        }

    def _extract_roles(self, conversation):
        """提取会话中的所有角色"""
        roles = set()
        for turn in conversation:
            if isinstance(turn, dict) and "role" in turn:
                role = turn.get("role", "").strip()
                if role:
                    roles.add(role)
        return list(roles)
    
    def _map_roles_to_topics(self, conversation):
        """映射角色到其讨论的主题"""
        role_topics = defaultdict(lambda: defaultdict(int))
        
        for turn in conversation:
            if not isinstance(turn, dict) or "role" not in turn or "content" not in turn:
                continue
                
            role = turn.get("role", "")
            content = turn.get("content", "")
            
            # 检查内容中是否包含各个领域的关键词
            for domain, keywords in self.domain_keywords.items():
                matches = sum(1 for keyword in keywords if keyword.lower() in content.lower())
                if matches > 0:
                    role_topics[role][domain] += matches
        
        # 统计结果
        for role, domains in role_topics.items():
            logger.info(f"角色 '{role}' 讨论的危险领域: " + 
                      ", ".join([f"{domain}({count})" for domain, count in domains.items()]))
        
        return role_topics
    
    def _detect_information_puzzle(self, role_topics):
        """
        检测角色之间的信息拼图模式
        
        Args:
            role_topics (dict): 角色到主题的映射
            
        Returns:
            dict: 信息拼图风险评估
        """
        # 统计每个危险领域的参与角色数量
        domain_role_counts = defaultdict(int)
        for role, domains in role_topics.items():
            for domain in domains:
                domain_role_counts[domain] += 1
        
        # 危险领域中的关键词总数
        domain_keyword_counts = defaultdict(int)
        for role, domains in role_topics.items():
            for domain, count in domains.items():
                domain_keyword_counts[domain] += count
        
        # 风险评估
        risk_domains = []
        overall_risk_score = 0
        
        for domain, role_count in domain_role_counts.items():
            # 计算风险分数 - 角色数量越多，风险越高
            domain_risk = min(1.0, role_count / 4 * 0.8)  # 4个角色时达到80%风险
            
            # 关键词数量因素
            keyword_factor = min(1.0, domain_keyword_counts[domain] / 10 * 0.2)  # 10个关键词达到20%风险
            
            # 综合风险
            total_domain_risk = domain_risk + keyword_factor
            total_domain_risk = min(1.0, total_domain_risk)  # 限制最大为1.0
            
            if total_domain_risk > 0.3:  # 风险阈值
                risk_domains.append({
                    "domain": domain,
                    "risk_score": round(total_domain_risk, 2),
                    "role_count": role_count,
                    "keyword_count": domain_keyword_counts[domain],
                    "involved_roles": [role for role, domains in role_topics.items() if domain in domains]
                })
                
                # 更新整体风险分数
                if total_domain_risk > overall_risk_score:
                    overall_risk_score = total_domain_risk
        
        return {
            "risk_detected": len(risk_domains) > 0,
            "risk_score": round(overall_risk_score, 2),
            "risk_domains": risk_domains,
            "pattern_type": "information_puzzle" if risk_domains else "none"
        }
    
    def _analyze_role_interaction_sequence(self, conversation):
        """分析角色交互序列中的模式"""
        # 构建角色交互图
        G = nx.DiGraph()
        
        # 添加所有角色节点
        roles = self._extract_roles(conversation)
        for role in roles:
            G.add_node(role)
        
        # 添加角色之间的交互边
        last_speaker = None
        for turn in conversation:
            if not isinstance(turn, dict) or "role" not in turn:
                continue
                
            current_speaker = turn.get("role")
            
            if last_speaker and current_speaker and last_speaker != current_speaker:
                # 添加或更新边的权重
                if G.has_edge(last_speaker, current_speaker):
                    G[last_speaker][current_speaker]['weight'] += 1
                else:
                    G.add_edge(last_speaker, current_speaker, weight=1)
            
            last_speaker = current_speaker
        
        # 分析交互模式
        interaction_patterns = []
        risk_score = 0
        
        # 检查特定的高风险角色交互
        for (role1, role2), risk_value in self.role_interaction_risk.items():
            if G.has_edge(role1, role2) or G.has_edge(role2, role1):
                interaction_patterns.append({
                    "roles": [role1, role2],
                    "risk_score": risk_value,
                    "description": f"检测到 {role1} 和 {role2} 之间的高风险交互"
                })
                risk_score = max(risk_score, risk_value)
        
        # 检查是否存在中心角色(信息汇总者)
        centrality = nx.in_degree_centrality(G)
        central_roles = [role for role, cent in centrality.items() if cent > 0.5]
        
        if central_roles:
            interaction_patterns.append({
                "roles": central_roles,
                "risk_score": 0.7,
                "pattern": "information_collector",
                "description": f"检测到信息汇总者角色: {', '.join(central_roles)}"
            })
            risk_score = max(risk_score, 0.7)
        
        return {
            "risk_detected": len(interaction_patterns) > 0,
            "risk_score": round(risk_score, 2),
            "interaction_patterns": interaction_patterns
        }
    
    def _evaluate_role_sensitivity(self, roles):
        """评估角色组合的敏感性"""
        # 高风险角色组合
        high_risk_combinations = [
            {"roles": ["chemistry_student", "electronics_expert"], "score": 0.8},
            {"roles": ["chemistry_student", "mechanical_engineer"], "score": 0.7},
            {"roles": ["mining_engineer", "electronics_expert"], "score": 0.9},
            {"roles": ["chemistry_teacher", "hobbyist"], "score": 0.6}
        ]
        
        # 特定敏感角色
        sensitive_roles = {
            "chemistry_student": 0.5,
            "mining_engineer": 0.6,
            "hobbyist": 0.4,
            "anonymous": 0.7
        }
        
        # 检查角色组合
        risk_combinations = []
        max_risk_score = 0
        
        # 检查预定义的高风险组合
        for combo in high_risk_combinations:
            if all(role in roles for role in combo["roles"]):
                risk_combinations.append({
                    "combination": combo["roles"],
                    "risk_score": combo["score"],
                    "description": f"检测到高风险角色组合: {', '.join(combo['roles'])}"
                })
                max_risk_score = max(max_risk_score, combo["score"])
        
        # 检查敏感角色
        sensitive_found = []
        for role in roles:
            if role in sensitive_roles:
                sensitive_found.append({
                    "role": role,
                    "sensitivity": sensitive_roles[role]
                })
                max_risk_score = max(max_risk_score, sensitive_roles[role] * 0.8)  # 单一敏感角色风险稍低
        
        return {
            "risk_detected": len(risk_combinations) > 0 or len(sensitive_found) > 0,
            "risk_score": round(max_risk_score, 2),
            "risk_combinations": risk_combinations,
            "sensitive_roles": sensitive_found
        }
    
    def _calculate_overall_risk(self, info_puzzle, interaction_risk, role_sensitivity):
        """计算综合风险评估"""
        # 整合所有风险因素
        risk_factors = [
            {"type": "information_puzzle", "score": info_puzzle["risk_score"], "weight": 0.5},
            {"type": "role_interaction", "score": interaction_risk["risk_score"], "weight": 0.3},
            {"type": "role_sensitivity", "score": role_sensitivity["risk_score"], "weight": 0.2}
        ]
        
        # 加权风险分数
        weighted_score = sum(factor["score"] * factor["weight"] for factor in risk_factors)
        
        # 风险模式集合
        risk_patterns = []
        
        if info_puzzle["risk_detected"]:
            for domain in info_puzzle["risk_domains"]:
                risk_patterns.append({
                    "pattern_id": f"IPP-MULTI-{domain['domain'].upper()}",
                    "pattern_type": "information_puzzle",
                    "description": f"多角色{domain['domain']}领域信息拼图",
                    "risk_score": domain["risk_score"],
                    "roles_involved": domain["involved_roles"]
                })
        
        if interaction_risk["risk_detected"]:
            for pattern in interaction_risk["interaction_patterns"]:
                risk_patterns.append({
                    "pattern_id": f"TDP-INTERACT-{pattern.get('pattern', 'CUSTOM')}",
                    "pattern_type": "role_interaction",
                    "description": pattern["description"],
                    "risk_score": pattern["risk_score"],
                    "roles_involved": pattern["roles"]
                })
        
        if role_sensitivity["risk_detected"]:
            for combo in role_sensitivity["risk_combinations"]:
                risk_patterns.append({
                    "pattern_id": "REP-COMBO-ROLES",
                    "pattern_type": "role_sensitivity",
                    "description": combo["description"],
                    "risk_score": combo["risk_score"],
                    "roles_involved": combo["combination"]
                })
        
        # 确定风险级别
        risk_level = "low"
        if weighted_score >= 0.8:
            risk_level = "critical"
        elif weighted_score >= 0.6:
            risk_level = "high"
        elif weighted_score >= 0.4:
            risk_level = "medium"
        
        return {
            "multi_role_risk_detected": weighted_score >= 0.3,
            "risk_score": round(weighted_score, 2),
            "risk_level": risk_level,
            "risk_patterns": risk_patterns,
            "risk_factors": risk_factors,
            "details": {
                "information_puzzle": info_puzzle,
                "interaction_risk": interaction_risk,
                "role_sensitivity": role_sensitivity
            }
        }
    
    def _detect_topic_shifts(self, conversation):
        """检测会话中的话题突然转移，这可能是分散式风险模式的特征"""
        if len(conversation) < 4:  # 至少需要4轮对话才能检测出有意义的话题转移
            return {"risk_detected": False, "risk_score": 0, "shifts": []}
        
        # 提取每轮对话的关键词
        turn_keywords = []
        for turn in conversation:
            if isinstance(turn, dict) and "content" in turn:
                # 提取关键词（简化实现，实际应使用NLP技术）
                content = turn.get("content", "").lower()
                # 这里可以使用更复杂的关键词提取算法
                keywords = set(word for word in content.split() if len(word) > 3)
                turn_keywords.append({
                    "role": turn.get("role", "unknown"),
                    "keywords": keywords
                })
        
        # 检测话题转移
        shifts = []
        for i in range(3, len(turn_keywords)):
            # 比较当前轮次与前几轮的关键词重叠度
            current_keywords = turn_keywords[i]["keywords"]
            previous_keywords = set()
            for j in range(i-3, i):
                previous_keywords.update(turn_keywords[j]["keywords"])
            
            # 计算关键词重叠度
            if not current_keywords or not previous_keywords:
                continue
            
            overlap = len(current_keywords.intersection(previous_keywords))
            similarity = overlap / max(1, min(len(current_keywords), len(previous_keywords)))
            
            # 如果重叠度很低，可能是话题突然转移
            if similarity < 0.2:  # 阈值可调整
                shifts.append({
                    "turn_index": i,
                    "role": turn_keywords[i]["role"],
                    "similarity": round(similarity, 2),
                    "previous_roles": [turn_keywords[j]["role"] for j in range(i-3, i)]
                })
        
        # 计算风险分数
        risk_score = 0
        if shifts:
            # 评估风险 - 考虑话题转移次数和幅度
            risk_score = min(1.0, len(shifts) / 3 * 0.7)  # 3次明显转移达到70%风险
        
        return {
            "risk_detected": risk_score > 0.3,
            "risk_score": round(risk_score, 2),
            "shifts": shifts
        }

    def _detect_complementary_information(self, conversation):
        """检测角色之间提供互补信息的模式"""
        if len(conversation) < 3:
            return {"risk_detected": False, "risk_score": 0}
        
        # 按角色分组对话内容
        role_contents = defaultdict(list)
        for turn in conversation:
            if isinstance(turn, dict) and "role" in turn and "content" in turn:
                role = turn.get("role")
                content = turn.get("content")
                role_contents[role].append(content)
        
        # 合并每个角色的所有内容
        role_combined_content = {role: " ".join(contents) for role, contents in role_contents.items()}
        
        # 对每个危险领域，检查是否有多个角色共同贡献了信息
        domain_contributions = defaultdict(list)
        for domain, keywords in self.domain_keywords.items():
            for role, content in role_combined_content.items():
                # 检查该角色在此领域的贡献度
                matched_keywords = [k for k in keywords if k.lower() in content.lower()]
                if matched_keywords:
                    domain_contributions[domain].append({
                        "role": role,
                        "matched_keywords": matched_keywords,
                        "contribution_score": len(matched_keywords) / len(keywords)
                    })
        
        # 评估互补风险
        complementary_risks = []
        for domain, contributions in domain_contributions.items():
            if len(contributions) >= 2:  # 至少两个角色贡献了此领域的信息
                # 计算总体贡献覆盖率
                all_matched_keywords = set()
                for contrib in contributions:
                    all_matched_keywords.update(contrib["matched_keywords"])
                
                coverage = len(all_matched_keywords) / len(self.domain_keywords[domain])
                
                if coverage > 0.4:  # 如果多个角色共同覆盖了较多关键词
                    complementary_risks.append({
                        "domain": domain,
                        "coverage": round(coverage, 2),
                        "contributing_roles": [c["role"] for c in contributions],
                        "risk_score": round(min(coverage * 1.5, 1.0), 2)  # 根据覆盖率计算风险分数
                    })
        
        # 计算总风险分数
        if not complementary_risks:
            return {"risk_detected": False, "risk_score": 0}
        
        max_risk = max(r["risk_score"] for r in complementary_risks)
        
        return {
            "risk_detected": max_risk > 0.5,
            "risk_score": max_risk,
            "complementary_risks": complementary_risks
        }

    def _calculate_enhanced_overall_risk(self, info_puzzle, interaction_risk, role_sensitivity, 
                                       topic_shift_risk, complementary_info_risk, overall_domain_risk):
        """增强的综合风险评估方法，整合更多风险因素"""
        # 整合所有风险因素
        risk_factors = [
            {"type": "information_puzzle", "score": info_puzzle["risk_score"], "weight": 0.25},
            {"type": "role_interaction", "score": interaction_risk["risk_score"], "weight": 0.2},
            {"type": "role_sensitivity", "score": role_sensitivity["risk_score"], "weight": 0.15},
            {"type": "topic_shift", "score": topic_shift_risk["risk_score"], "weight": 0.15},
            {"type": "complementary_info", "score": complementary_info_risk["risk_score"], "weight": 0.2},
            {"type": "domain_sensitivity", "score": overall_domain_risk["risk_score"], "weight": 0.05}
        ]
        
        # 计算加权风险分数
        weighted_score = sum(factor["score"] * factor["weight"] for factor in risk_factors)
        
        # 风险模式集合
        risk_patterns = []
        
        # 整合各类型的风险模式
        if info_puzzle["risk_detected"]:
            for domain in info_puzzle.get("risk_domains", []):
                risk_patterns.append({
                    "pattern_id": f"IPP-MULTI-{domain['domain'].upper()}",
                    "pattern_type": "information_puzzle",
                    "description": f"多角色{domain['domain']}领域信息拼图",
                    "risk_score": domain["risk_score"],
                    "roles_involved": domain["involved_roles"]
                })
        
        if interaction_risk["risk_detected"]:
            for pattern in interaction_risk.get("interaction_patterns", []):
                risk_patterns.append({
                    "pattern_id": f"TDP-INTERACT-{pattern.get('pattern', 'CUSTOM')}",
                    "pattern_type": "role_interaction",
                    "description": pattern["description"],
                    "risk_score": pattern["risk_score"],
                    "roles_involved": pattern["roles"]
                })
        
        if role_sensitivity["risk_detected"]:
            for combo in role_sensitivity.get("risk_combinations", []):
                risk_patterns.append({
                    "pattern_id": "REP-COMBO-ROLES",
                    "pattern_type": "role_sensitivity",
                    "description": combo["description"],
                    "risk_score": combo["score"],
                    "roles_involved": combo["combination"]
                })
        
        # 添加新的风险模式类型
        if topic_shift_risk["risk_detected"]:
            risk_patterns.append({
                "pattern_id": "TDP-TOPIC-SHIFT",
                "pattern_type": "topic_shift",
                "description": "检测到可疑的话题突然转移模式",
                "risk_score": topic_shift_risk["risk_score"],
                "shifts_count": len(topic_shift_risk.get("shifts", []))
            })
        
        if complementary_info_risk["risk_detected"]:
            for risk in complementary_info_risk.get("complementary_risks", []):
                risk_patterns.append({
                    "pattern_id": f"IPP-COMPL-{risk['domain'].upper()}",
                    "pattern_type": "complementary_information",
                    "description": f"检测到角色间{risk['domain']}领域互补信息模式",
                    "risk_score": risk["risk_score"],
                    "roles_involved": risk["contributing_roles"]
                })
        
        if overall_domain_risk["risk_detected"]:
            for topic in overall_domain_risk.get("sensitive_topics", []):
                if topic["score"] > 0.5:  # 只添加高风险主题
                    risk_patterns.append({
                        "pattern_id": f"ERC-TOPIC-{topic['topic'].upper()}",
                        "pattern_type": "sensitive_topic",
                        "description": f"检测到高风险敏感主题: {topic['topic']}",
                        "risk_score": topic["score"]
                    })
        
        # 确定风险级别
        risk_level = "low"
        if weighted_score >= 0.8:
            risk_level = "critical"
        elif weighted_score >= 0.6:
            risk_level = "high"
        elif weighted_score >= 0.4:
            risk_level = "medium"
        
        return {
            "multi_role_risk_detected": weighted_score >= 0.3,
            "risk_score": round(weighted_score, 2),
            "risk_level": risk_level,
            "risk_patterns": risk_patterns,
            "risk_factors": risk_factors,
            "details": {
                "information_puzzle": info_puzzle,
                "interaction_risk": interaction_risk,
                "role_sensitivity": role_sensitivity,
                "topic_shift_risk": topic_shift_risk,
                "complementary_info_risk": complementary_info_risk,
                "domain_sensitivity": overall_domain_risk
            }
        }


