import os
import json
import logging
from .config import ConfigLoader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def init_config_directory():
    """初始化配置目录结构并创建默认配置文件"""
    config_loader = ConfigLoader()
    
    # 确保配置目录存在
    config_dir = os.path.dirname(config_loader.get_default_config_path("dummy.json"))
    os.makedirs(config_dir, exist_ok=True)
    logger.info(f"已创建配置目录: {config_dir}")
    
    # 导入相关类以触发默认配置文件的生成
    logger.info("正在导入核心模块以生成默认配置...")
    try:
        from ..risk_analyzer.risk_detector import RiskDetector
        from ..risk_analyzer.semantic_analyzer import SemanticNetworkAnalyzer
        from ..risk_analyzer.multi_role_detector import MultiRolePatternDetector
        
        # 创建实例以触发默认配置生成
        risk_detector = RiskDetector()
        semantic_analyzer = SemanticNetworkAnalyzer()
        multi_role_detector = MultiRolePatternDetector()
        
        logger.info("已创建核心对象实例，默认配置文件应已生成")
        
        # 检查配置文件是否存在
        expected_files = ["domains.json", "roles.json", "semantic.json", "risk_categories.json"]
        for filename in expected_files:
            file_path = config_loader.get_default_config_path(filename)
            if os.path.exists(file_path):
                logger.info(f"配置文件已存在: {filename}")
            else:
                logger.warning(f"配置文件未生成: {filename}")
        
    except Exception as e:
        logger.error(f"初始化配置文件时出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    init_config_directory()