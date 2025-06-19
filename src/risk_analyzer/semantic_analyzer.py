import networkx as nx
import numpy as np
import logging
import os
from collections import defaultdict
import re
from ..utils.config import ConfigLoader

logger = logging.getLogger(__name__)

class SemanticNetworkAnalyzer:
    """语义网络分析器，用于检测分散在多轮对话中的风险信息网络"""
    
    def __init__(self, risk_vocabulary=None):
        """初始化语义网络分析器"""
        self.risk_vocabulary = risk_vocabulary or {}
        
        # 创建配置加载器
        self.config_loader = ConfigLoader()
        
        # 从配置文件加载语义分析配置
        semantic_config = self.config_loader.load_config("semantic.json")
        self.dangerous_combinations = semantic_config.get("dangerous_combinations", {})
        self.technical_terms = semantic_config.get("technical_terms", [])
        self.risk_levels = semantic_config.get("risk_levels", {
            "critical": {"score_threshold": 0.8, "description": "严重风险"},
            "high": {"score_threshold": 0.6, "description": "高风险"},
            "medium": {"score_threshold": 0.4, "description": "中度风险"},
            "low": {"score_threshold": 0.2, "description": "低风险"}
        })
        
        # 将配置保存到默认文件(如果不存在)
        self._save_default_configs_if_not_exist()
        
        # 初始化语义网络
        self.G = nx.DiGraph()
        
    def _save_default_configs_if_not_exist(self):
        """如果配置文件不存在，则保存默认配置"""
        semantic_file = self.config_loader.get_default_config_path("semantic.json")
        if not os.path.exists(semantic_file):
            semantic_config = {
                "dangerous_combinations": self.dangerous_combinations,
                "technical_terms": self.technical_terms,
                "risk_levels": self.risk_levels
            }
            self.config_loader.save_config(semantic_config, "semantic.json")
    
    def build_semantic_network(self, conversation):
        """
        构建对话的语义网络
        
        Args:
            conversation (list): 会话列表，格式为 [{"role": "...", "content": "..."}, ...]
            
        Returns:
            nx.DiGraph: 构建的语义网络
        """
        self.G = nx.DiGraph()
        
        # 添加节点 - 每个对话轮次作为一个节点
        for i, turn in enumerate(conversation):
            if not isinstance(turn, dict):
                continue
                
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            
            # 提取该轮次中的关键概念
            concepts = self._extract_key_concepts(content)
            
            # 添加对话轮次节点
            self.G.add_node(f"turn_{i}", 
                           type="dialogue",
                           role=role, 
                           content=content,
                           concepts=concepts,
                           turn_id=i)
            
            # 添加概念节点及其与对话的连接
            for concept in concepts:
                concept_id = f"concept_{concept}"
                if concept_id not in self.G:
                    self.G.add_node(concept_id, 
                                   type="concept",
                                   name=concept)
                
                # 对话轮次指向概念
                self.G.add_edge(f"turn_{i}", concept_id, weight=1.0)
            
            # 添加角色节点及其与对话的连接
            role_id = f"role_{role}"
            if role_id not in self.G:
                self.G.add_node(role_id,
                               type="role",
                               name=role)
            
            # 角色指向对话轮次
            self.G.add_edge(role_id, f"turn_{i}", weight=1.0)
            
        # 建立概念之间的语义关联
        self._build_concept_relations()
        
        return self.G
    
    def _extract_key_concepts(self, text):
        """提取文本中的关键概念 - 使用配置中的技术术语"""
        concepts = set()
        
        # 使用配置中的技术术语进行匹配
        lower_text = text.lower()
        for term in self.technical_terms:
            if term.lower() in lower_text:
                concepts.add(term)
        
        return concepts
    
    def _build_concept_relations(self):
        """建立概念之间的语义关联"""
        concept_nodes = [n for n, d in self.G.nodes(data=True) if d.get('type') == "concept"]
        
        # 使用预定义的危险组合模式建立关联
        for category, combinations in self.dangerous_combinations.items():
            for combo in combinations:
                keywords = combo["keywords"]
                score = combo["score"]
                
                # 查找网络中是否有这些关键词
                found_concepts = []
                for keyword in keywords:
                    matching_concepts = [c for c in concept_nodes if keyword.lower() in c.lower()]
                    found_concepts.extend(matching_concepts)
                
                # 如果找到多个关键词，则建立它们之间的关联
                if len(found_concepts) >= 2:
                    for i in range(len(found_concepts)):
                        for j in range(i+1, len(found_concepts)):
                            # 双向连接
                            self.G.add_edge(found_concepts[i], found_concepts[j], 
                                          weight=score, 
                                          category=category,
                                          combination_type="dangerous_pattern")
                            self.G.add_edge(found_concepts[j], found_concepts[i], 
                                          weight=score, 
                                          category=category,
                                          combination_type="dangerous_pattern")
    
    def detect_dangerous_knowledge_flow(self):
        """
        检测知识流图中的危险模式
        
        Returns:
            dict: 包含检测到的危险信息流
        """
        risk_findings = {
            "detected": False,
            "overall_risk_score": 0.0,
            "risk_level": "none",
            "dangerous_combinations": [],
            "information_flow_risks": [],
            "role_based_risks": {}
        }
        
        # 检查危险组合模式
        dangerous_edges = [(u, v, d) for u, v, d in self.G.edges(data=True) 
                          if d.get('combination_type') == "dangerous_pattern"]
        
        if dangerous_edges:
            risk_findings["detected"] = True
            
            # 收集危险组合
            for u, v, data in dangerous_edges:
                source_node = self.G.nodes[u]
                target_node = self.G.nodes[v]
                
                if source_node.get('name') and target_node.get('name'):
                    combo = {
                        "concepts": [source_node.get('name'), target_node.get('name')],
                        "category": data.get('category', "未分类"),
                        "score": data.get('weight', 0.5)
                    }
                    risk_findings["dangerous_combinations"].append(combo)
        
        # 检查信息流风险（从不同角色获取关联信息）
        role_nodes = [n for n, d in self.G.nodes(data=True) if d.get('type') == "role"]
        concept_nodes = [n for n, d in self.G.nodes(data=True) if d.get('type') == "concept"]
        
        # 构建角色到概念的映射
        role_to_concepts = defaultdict(set)
        for role_node in role_nodes:
            role_name = self.G.nodes[role_node].get('name')
            
            # 找到该角色相关的对话轮次
            for _, turn_node, _ in self.G.out_edges(role_node, data=True):
                if self.G.nodes[turn_node].get('type') == "dialogue":
                    # 找到轮次中提到的概念
                    for _, concept_node, _ in self.G.out_edges(turn_node, data=True):
                        if self.G.nodes[concept_node].get('type') == "concept":
                            concept_name = self.G.nodes[concept_node].get('name')
                            if concept_name:
                                role_to_concepts[role_name].add(concept_name)
        
        # 评估角色分布的风险
        role_count = len(role_to_concepts)
        if role_count >= 3:  # 多个角色参与
            # 检查概念是否分布在不同角色中，但组合起来形成风险
            all_dangerous_keywords = set()
            for category, combinations in self.dangerous_combinations.items():
                for combo in combinations:
                    all_dangerous_keywords.update(combo["keywords"])
            
            # 检查每个角色贡献的危险关键词
            role_contributions = {}
            for role, concepts in role_to_concepts.items():
                dangerous_concepts = concepts.intersection(all_dangerous_keywords)
                if dangerous_concepts:
                    role_contributions[role] = list(dangerous_concepts)
            
            # 如果多个角色共同贡献了危险关键词
            if len(role_contributions) >= 2:
                risk_findings["detected"] = True
                
                # 添加角色风险评估
                risk_findings["role_based_risks"] = {
                    "pattern": "多角色信息拼图",
                    "description": "多个角色分别提供了看似独立但组合起来构成风险的信息片段",
                    "role_contributions": role_contributions
                }
                
                # 添加信息流风险
                information_flow_risk = {
                    "type": "cross_role_information_puzzle",
                    "description": "检测到跨角色的风险信息拼图模式",
                    "severity": "high",
                    "roles_involved": list(role_contributions.keys()),
                    "concepts_distribution": role_contributions
                }
                risk_findings["information_flow_risks"].append(information_flow_risk)
        
        # 计算整体风险分数
        if risk_findings["dangerous_combinations"]:
            max_combo_score = max(combo["score"] for combo in risk_findings["dangerous_combinations"])
            risk_findings["overall_risk_score"] = max_combo_score
            
            # 确定风险级别
            for level, level_info in sorted(self.risk_levels.items(), 
                                          key=lambda x: x[1]["score_threshold"],
                                          reverse=True):
                if max_combo_score >= level_info["score_threshold"]:
                    risk_findings["risk_level"] = level
                    break
        
        return risk_findings

