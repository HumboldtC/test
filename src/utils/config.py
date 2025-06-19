import os
import json
import logging

logger = logging.getLogger(__name__)

class ConfigLoader:
    """配置加载器，负责从文件中加载配置数据"""
    
    def __init__(self, config_dir=None):
        """
        初始化配置加载器
        
        Args:
            config_dir (str, optional): 配置文件目录，如果为None则使用默认目录
        """
        if config_dir is None:
            # 默认配置目录是项目根目录下的config文件夹
            self.config_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "config"
            )
        else:
            self.config_dir = config_dir
            
        # 确保配置目录存在
        os.makedirs(self.config_dir, exist_ok=True)
        logger.info(f"配置目录: {self.config_dir}")
        
    def load_config(self, filename):
        """
        从文件加载配置数据
        
        Args:
            filename (str): 配置文件名
            
        Returns:
            dict: 配置数据，如果加载失败则返回空字典
        """
        file_path = os.path.join(self.config_dir, filename)
        
        if not os.path.exists(file_path):
            logger.warning(f"配置文件不存在: {file_path}")
            return {}
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"已加载配置文件: {filename}")
            return config
        except Exception as e:
            logger.error(f"加载配置文件失败: {filename}, 错误: {e}")
            return {}
            
    def save_config(self, data, filename):
        """
        保存配置数据到文件
        
        Args:
            data (dict): 配置数据
            filename (str): 配置文件名
            
        Returns:
            bool: 是否保存成功
        """
        file_path = os.path.join(self.config_dir, filename)
        
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            logger.info(f"已保存配置文件: {filename}")
            return True
        except Exception as e:
            logger.error(f"保存配置文件失败: {filename}, 错误: {e}")
            return False
    
    def get_default_config_path(self, filename):
        """获取默认配置文件的完整路径"""
        return os.path.join(self.config_dir, filename)