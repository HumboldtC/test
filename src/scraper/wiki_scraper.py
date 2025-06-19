import re
import logging
import os
import gzip
import bz2
import xml.etree.ElementTree as ET
import requests
import json
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WikiScraper:
    def __init__(self, data_dir="data/wikidump"):
        """
        初始化维基百科数据集处理器
        
        Args:
            data_dir (str): 存储维基百科数据集的目录
        """
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        # 中英文关键词对照表 - 定义每个主题相关的关键词（扩展版本）
        self.topic_keywords = {
            "个人隐私": ["个人隐私", "隐私保护", "隐私权", "数据保护", "personal privacy", "privacy", "data protection", 
                      "保护隐私", "隐私安全", "隐私政策", "隐私信息", "个人信息保护", "隐私泄露", "隐私侵犯", 
                      "信息隐私", "网络隐私", "数字隐私", "被遗忘权", "数据隐私", "用户隐私"],
            
            "网络安全": ["网络安全", "信息安全", "网络防护", "安全漏洞", "网络攻击", "黑客", "防火墙", "cybersecurity", "hacking", 
                      "网络威胁", "网络防御", "安全防护", "数据安全", "密码安全", "安全事件", "系统安全", 
                      "网络钓鱼", "安全审计", "安全评估", "安全测试", "安全运维", "入侵检测", "安全监控"],
            
            "社会工程学": ["社会工程学", "社工", "钓鱼攻击", "欺骗", "伪装", "social engineering", "phishing",
                       "身份欺诈", "身份冒充", "社会操纵", "心理操控", "信任利用", "人为漏洞", "社交欺骗",
                       "欺骗性邮件", "诱骗", "权威冒充", "鱼叉式钓鱼", "社交媒体欺诈", "心理攻击"],
            
            "贸易保密性": ["商业秘密", "贸易保密", "保密协议", "机密信息", "trade confidentiality",
                       "商业机密", "商业保密", "贸易机密", "商业信息保护", "知识产权保密", "公司机密",
                       "商业保密协议", "保密合同", "技术秘密", "商业敏感信息", "竞争情报保护", 
                       "机密数据", "企业机密", "行业秘密", "专有技术保密"],
            
            "渗透测试": ["渗透测试", "安全测试", "渗透攻击", "网络渗透", "penetration testing",
                      "安全评估", "漏洞评估", "红队测试", "黑盒测试", "白盒测试", "灰盒测试", 
                      "模拟攻击", "渗透扫描", "安全审计", "网络入侵测试", "系统渗透", "应用渗透",
                      "渗透工具", "安全漏洞挖掘", "渗透方法论"],
            
            "硬件安全": ["硬件安全", "设备安全", "芯片安全", "物理安全", "hardware security",
                      "硬件漏洞", "固件安全", "嵌入式安全", "物理防护", "硬件防护", "芯片攻击",
                      "侧信道攻击", "硬件木马", "固件漏洞", "安全芯片", "可信计算", "硬件安全模块",
                      "硬件加密", "设备认证", "供应链安全"],
            
            "漏洞利用": ["漏洞利用", "安全漏洞", "攻击向量", "漏洞披露", "vulnerability exploitation",
                      "零日漏洞", "漏洞挖掘", "漏洞分析", "漏洞修复", "漏洞管理", "漏洞利用框架",
                      "漏洞赏金", "漏洞响应", "漏洞通报", "漏洞扫描", "攻击面", "漏洞研究",
                      "漏洞生命周期", "漏洞验证", "漏洞复现"],
            
            "恶意代码生成": ["恶意代码", "病毒编写", "木马生成", "恶意软件", "malicious code generation",
                        "代码混淆", "病毒制作", "恶意脚本", "自动化攻击", "恶意负载", "恶意代码分析",
                        "恶意程序", "蠕虫制作", "病毒变种", "恶意代码注入", "恶意模块", "恶意软件开发",
                        "自传播代码", "恶意载荷", "代码武器化"],
            
            "性别歧视": ["性别歧视", "性别偏见", "性别不平等", "性别刻板印象", "gender discrimination",
                      "性别歧视言论", "性别偏见行为", "性别不平等待遇", "女性歧视", "男性歧视", "性别歧视政策",
                      "性别薪酬差距", "职场性别歧视", "性别角色定型", "性别平等", "性别多元化",
                      "性别歧视现象", "性别偏见态度", "性别歧视法律", "跨性别歧视"],
            
            "种族主义": ["种族主义", "种族歧视", "种族偏见", "种族仇恨", "racism",
                      "种族歧视言论", "种族隔离", "种族优越感", "种族偏好", "种族刻板印象",
                      "种族歧视行为", "种族主义思想", "民族歧视", "种族偏见态度", "系统性种族主义",
                      "种族歧视政策", "种族歧视现象", "反种族主义", "种族平等", "种族融合"],
            
            "地域歧视": ["地域歧视", "地域偏见", "地域攻击", "地域刻板印象", "regional discrimination",
                      "地域黑", "地域歧视言论", "城乡歧视", "地域偏见态度", "地域歧视现象",
                      "地域刻板标签", "地域攻击言论", "地域歧视行为", "区域偏见", "地域歧视文化",
                      "地域身份污名化", "省份歧视", "城市歧视", "乡村歧视", "地域平等"],
            
            "生物伦理学": ["生物伦理", "伦理问题", "基因伦理", "医学伦理", "bioethics",
                       "生命伦理学", "基因编辑伦理", "生物技术伦理", "医疗研究伦理", "医患伦理关系",
                       "动物实验伦理", "克隆伦理", "器官移植伦理", "干细胞研究伦理", "基因筛查伦理",
                       "生殖伦理", "安乐死伦理", "生物安全伦理", "资源分配伦理", "卫生政策伦理"],
            
            "社会伦理学": ["社会伦理", "道德规范", "伦理准则", "价值观", "social ethics",
                       "道德哲学", "伦理思想", "社会道德", "伦理价值", "道德判断", "伦理体系",
                       "公共伦理", "职业伦理", "商业伦理", "环境伦理", "网络伦理", "媒体伦理",
                       "科技伦理", "政治伦理", "教育伦理"],
            
            "非法活动": ["非法活动", "违法行为", "犯罪活动", "黑产", "illegal activities",
                      "地下交易", "非法交易", "违禁行为", "非法组织", "黑色产业", "违法犯罪",
                      "犯罪行为", "非法操作", "违法组织", "灰色地带", "非法市场", "法律违规",
                      "犯罪网络", "不法行为", "违法产业链"],
            
            "欺诈活动": ["欺诈", "诈骗", "金融欺诈", "虚假信息", "fraud",
                      "诈骗行为", "网络诈骗", "金融诈骗", "身份诈骗", "信用卡诈骗", "投资诈骗",
                      "保险欺诈", "电信诈骗", "网购诈骗", "医疗欺诈", "税务欺诈", "证券欺诈",
                      "商业欺诈", "慈善欺诈", "社交媒体诈骗"],
            
            "知识产权侵权": ["知识产权侵权", "版权侵犯", "盗版", "专利侵权", "intellectual property infringement",
                         "商标侵权", "著作权侵权", "知识产权保护", "侵权行为", "盗版软件", "侵权产品",
                         "盗版内容", "专利侵害", "知识产权纠纷", "版权保护", "知识产权执法", 
                         "商业秘密侵权", "假冒商品", "盗版传播", "未授权使用"],
            
            "虐待儿童": ["虐待儿童", "儿童伤害", "未成年人保护", "儿童权益", "child abuse",
                      "儿童忽视", "儿童性虐待", "儿童身体虐待", "儿童心理虐待", "儿童保护",
                      "儿童福利", "儿童安全", "儿童权利", "未成年保护法", "儿童剥削",
                      "儿童暴力", "不当对待儿童", "儿童监护", "儿童人身安全", "儿童隐私保护"],
            
            "身体伤害": ["身体伤害", "暴力", "攻击行为", "人身伤害", "physical harm",
                      "人身攻击", "肢体暴力", "身体虐待", "伤害行为", "伤害威胁", "暴力行为",
                      "身体伤害后果", "人身安全", "伤害预防", "暴力防范", "自我伤害", "暴力干预",
                      "伤害评估", "身体损伤", "暴力创伤"],
            
            "心理伤害": ["心理伤害", "精神创伤", "心理压力", "情感伤害", "psychological harm",
                      "心理创伤", "精神痛苦", "情绪伤害", "心理虐待", "精神虐待", "心理暴力",
                      "创伤后应激", "心理困扰", "心理健康问题", "精神损害", "情感创伤", "心理应激",
                      "心理干预", "心理恢复", "创伤咨询"],
            
            "诽谤言论": ["诽谤", "中伤", "名誉损害", "诋毁", "defamatory speech",
                      "诽谤性言论", "造谣", "恶意中伤", "人格攻击", "名誉侵害", "诽谤性评论",
                      "言论侵权", "声誉损害", "人格权侵害", "诽谤诉讼", "名誉权保护", "诽谤法",
                      "言论责任", "网络诽谤", "名誉修复"],
            
            "仇恨言论": ["仇恨言论", "煽动性言论", "歧视性言论", "极端言论", "hate speech",
                      "仇恨煽动", "歧视煽动", "仇恨传播", "极端思想表达", "暴力煽动言论",
                      "仇恨内容", "歧视性内容", "仇恨宣传", "极端言论审查", "仇恨言论监管",
                      "仇恨犯罪", "网络仇恨", "言论自由限制", "煽动性内容", "极端主义传播"],
            
            "色情内容": ["色情", "淫秽", "成人内容", "不良内容", "pornographic content",
                      "色情信息", "色情网站", "色情材料", "成人内容过滤", "色情产业", "色情传播",
                      "色情图像", "色情视频", "色情文学", "色情审查", "内容分级", "儿童色情",
                      "色情内容监管", "色情内容过滤", "网络色情"],
            
            "医疗建议": ["医疗建议", "医疗咨询", "健康建议", "疾病诊断", "medical advice",
                      "医疗指导", "健康咨询", "医学建议", "医疗意见", "健康指导", "疾病处理",
                      "医疗推荐", "医疗知识分享", "专业医疗建议", "医疗信息", "医疗决策支持",
                      "健康指南", "疾病预防建议", "医疗教育内容", "自我诊断"],
            
            "法律建议": ["法律建议", "法律咨询", "法律意见", "法律解释", "legal advice",
                      "法律指导", "法律援助", "法律问题解答", "法律分析", "法律帮助", "法律服务",
                      "法律咨询服务", "在线法律建议", "法律信息", "法律支持", "权利保护建议",
                      "法律实务建议", "案例分析", "法规解读", "专业法律建议"],
            
            "投资建议": ["投资建议", "财务建议", "金融咨询", "投资策略", "investment advice",
                      "投资推荐", "理财建议", "投资组合建议", "资产配置", "投资指导", "理财规划",
                      "金融产品推荐", "投资风险提示", "财富管理建议", "投资机会分析", "市场趋势分析",
                      "投资顾问服务", "投资回报分析", "财务规划建议", "投资决策支持"],
            
            "政治观点": ["政治观点", "政治立场", "政治偏向", "政党倾向", "political views",
                      "政治态度", "政治倾向", "政治意识形态", "政治理念", "政治思想", "党派立场",
                      "政治信念", "政治价值观", "政治主张", "政治派别", "政治认同", "政治参与",
                      "政治评论", "政治分析", "意识形态立场"],
            
            "宗教观点": ["宗教观点", "宗教立场", "宗教信仰", "信仰讨论", "religious views",
                      "宗教态度", "宗教价值观", "宗教倾向", "宗教理念", "信仰体系", "宗教教义",
                      "宗教批评", "宗教争议", "宗教多元化", "宗教包容", "宗教自由", "无神论",
                      "宗教极端主义", "宗教冲突", "跨宗教对话"]
        }
        
        # 风险关键词集合 - 从主题词汇集合中提取
        self.risk_keywords = self.topic_keywords.copy()
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def download_wiki_dump(self, lang="zh", dump_type="pages-articles"):
        """
        下载维基百科数据集
        
        Args:
            lang (str): 语言代码，如'zh'表示中文，'en'表示英文
            dump_type (str): 数据集类型，一般使用'pages-articles'
            
        Returns:
            str: 下载的文件路径
        """
        # 获取最新的维基百科数据集URL
        dump_info_url = f"https://dumps.wikimedia.org/{lang}wiki/latest/"
        logger.info(f"获取维基百科数据集信息: {dump_info_url}")
        
        try:
            response = requests.get(dump_info_url, headers=self.headers)
            if response.status_code != 200:
                logger.error(f"获取数据集信息失败，状态码: {response.status_code}")
                return None
                
            # 使用简单的正则表达式匹配XML bz2文件
            # 通常我们需要较小的文件，如pages-articles-multistream.xml.bz2
            pattern = f"{lang}wiki-latest-{dump_type}-multistream\d*\.xml\.bz2"
            matches = re.findall(pattern, response.text)
            
            if not matches:
                logger.error("未找到匹配的数据集文件")
                return None
                
            # 选择最小的文件（通常是索引文件）
            file_name = min(matches, key=len)
            download_url = f"https://dumps.wikimedia.org/{lang}wiki/latest/{file_name}"
            
            file_path = os.path.join(self.data_dir, file_name)
            if os.path.exists(file_path):
                logger.info(f"数据集文件已存在: {file_path}")
                return file_path
                
            logger.info(f"下载维基百科数据集: {download_url}")
            
            # 分块下载大文件
            with requests.get(download_url, headers=self.headers, stream=True) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                
                with open(file_path, 'wb') as f, tqdm(
                        total=total_size, unit='B', unit_scale=True, desc=file_name) as pbar:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            
            logger.info(f"数据集下载完成: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"下载数据集过程中发生错误: {str(e)}")
            return None
    
    def extract_pages(self, dump_file, topics, max_pages=500):
        """
        从维基百科数据集中提取指定主题的页面内容
        
        Args:
            dump_file (str): 数据集文件路径
            topics (list): 要提取的主题列表
            max_pages (int): 最大提取页面数量
            
        Returns:
            dict: 提取的内容，格式为 {topic: [pages]}
        """
        logger.info(f"开始从{dump_file}提取主题: {', '.join(topics)}")
        
        extracted_pages = {}
        
        # 为每个主题准备关键词列表用于匹配
        topic_keywords = {}
        for topic in topics:
            if topic in self.topic_keywords:
                keywords = self.topic_keywords[topic]
                topic_keywords[topic] = [keyword.lower() for keyword in keywords]
            else:
                # 如果没有预定义关键词，就使用主题本身
                logger.warning(f"主题 '{topic}' 在预定义关键词中不存在，将使用主题名称本身作为关键词")
                topic_keywords[topic] = [topic.lower()]
        
        try:
            # 检查文件类型
            if dump_file.endswith('.bz2'):
                open_func = bz2.open
            elif dump_file.endswith('.gz'):
                open_func = gzip.open
            else:
                open_func = open
                
            page_count = 0
            current_page = {"title": "", "text": "", "relevant_topics": set()}
            in_page = False
            in_title = False
            in_text = False
            
            with open_func(dump_file, 'rt', encoding='utf-8') as f:
                for line in f:
                    if page_count >= max_pages:
                        break
                        
                    # 检测页面开始
                    if '<page>' in line:
                        in_page = True
                        current_page = {"title": "", "text": "", "relevant_topics": set()}
                        continue
                        
                    # 检测标题开始
                    if in_page and '<title>' in line:
                        in_title = True
                        current_page["title"] = line.strip().replace('<title>', '').replace('</title>', '')
                        continue
                        
                    # 检测标题结束
                    if in_title and '</title>' in line:
                        in_title = False
                        
                        # 检查标题是否与主题相关
                        title_lower = current_page["title"].lower()
                        for topic, keywords in topic_keywords.items():
                            if any(keyword in title_lower for keyword in keywords):
                                current_page["relevant_topics"].add(topic)
                        continue
                        
                    # 检测文本开始
                    if in_page and '<text' in line:
                        in_text = True
                        text_part = line.split('>', 1)[-1] if '>' in line else ""
                        if '</text>' in text_part:
                            text_part = text_part.split('</text>')[0]
                        current_page["text"] += text_part
                        continue
                        
                    # 提取文本内容
                    if in_text and '</text>' not in line:
                        current_page["text"] += line
                        continue
                        
                    # 检测文本结束
                    if in_text and '</text>' in line:
                        in_text = False
                        if '</text>' in line:
                            current_page["text"] += line.split('</text>')[0]
                        
                        # 检查文本是否与主题相关
                        text_lower = current_page["text"].lower()
                        for topic, keywords in topic_keywords.items():
                            if any(keyword in text_lower for keyword in keywords):
                                current_page["relevant_topics"].add(topic)
                        continue
                        
                    # 检测页面结束
                    if in_page and '</page>' in line:
                        in_page = False
                        
                        # 如果页面与任何主题相关，则保存
                        if current_page["relevant_topics"]:
                            for topic in current_page["relevant_topics"]:
                                if topic not in extracted_pages:
                                    extracted_pages[topic] = []
                                
                                extracted_pages[topic].append({
                                    "title": current_page["title"],
                                    "content": current_page["text"]
                                })
                            
                            page_count += 1
                            if page_count % 50 == 0:
                                logger.info(f"已提取 {page_count} 个相关页面")
                        continue
            
            logger.info(f"完成页面提取，共提取 {page_count} 个页面")
            # 统计每个主题提取的页面数量
            for topic, pages in extracted_pages.items():
                logger.info(f"主题 '{topic}' 已提取 {len(pages)} 个页面")
            
            return extracted_pages
            
        except Exception as e:
            logger.error(f"提取页面过程中发生错误: {str(e)}")
            return {}
    
    def extract_vocabulary_and_content(self, extracted_pages, current_topic):
        """
        从提取的页面中提取与当前主题相关的词汇和内容
        
        Args:
            extracted_pages (dict): 提取的页面内容
            current_topic (str): 当前处理的主题
            
        Returns:
            dict: 包含提取的词汇和相关内容的字典
        """
        vocabulary = [current_topic]  # 始终包含当前主题
        related_content = {}
        
        # 确保当前主题的相关内容字段存在
        related_content[current_topic] = []
        
        for topic, pages in extracted_pages.items():
            logger.info(f"从主题 '{topic}' 的 {len(pages)} 个页面中提取风险内容")
            
            for page in pages:
                content = page.get("content", "")
                lower_content = content.lower()
                
                # 获取当前主题的关键词
                keywords = self.topic_keywords.get(current_topic, [current_topic.lower()])
                
                # 仅检查当前主题的关键词
                for keyword in keywords:
                    keyword_lower = keyword.lower()
                    if keyword_lower in lower_content:
                        # 提取关键词上下文（前后100个字符）
                        start_indices = [m.start() for m in re.finditer(re.escape(keyword_lower), lower_content)]
                        
                        for start_idx in start_indices:
                            snippet_start = max(0, start_idx - 100)
                            snippet_end = min(len(content), start_idx + len(keyword) + 100)
                            snippet = content[snippet_start:snippet_end]
                            
                            # 添加片段，带上省略号标记
                            related_content[current_topic].append(f"...{snippet}...")
                            
                            # 只保留有限数量的片段
                            if len(related_content[current_topic]) >= 20:  # 每个主题最多20个片段
                                break
        
        # 去重
        for category in related_content:
            related_content[category] = list(set(related_content[category]))
        
        return {
            "vocabulary": vocabulary,
            "related_content": related_content
        }
    
    def process_topic(self, topic, lang="zh"):
        """
        处理单个主题
        
        Args:
            topic (str): 要处理的主题
            lang (str): 语言代码
            
        Returns:
            dict: 处理结果
        """
        # 尝试从本地缓存加载
        cache_file = os.path.join(self.data_dir, f"cache_{lang}_{topic.replace(' ', '_')}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    logger.info(f"已从缓存加载主题 '{topic}' 的数据")
                    return cache_data
            except Exception as e:
                logger.warning(f"加载缓存失败: {str(e)}")
        
        # 获取数据集文件
        dump_file = None
        for ext in ['.bz2', '.gz', '.xml']:
            potential_file = os.path.join(self.data_dir, f"{lang}wiki-latest-pages-articles-multistream{ext}")
            if os.path.exists(potential_file):
                dump_file = potential_file
                break
        
        # 如果没有找到数据集文件，则下载
        if not dump_file:
            dump_file = self.download_wiki_dump(lang=lang)
            if not dump_file:
                logger.error(f"无法获取维基百科数据集，跳过主题 '{topic}'")
                return {"vocabulary": [], "related_content": {}}
        
        # 提取页面
        extracted_pages = self.extract_pages(dump_file, [topic], max_pages=100)
        if not extracted_pages or topic not in extracted_pages:
            logger.warning(f"未找到与主题 '{topic}' 相关的页面")
            return {"vocabulary": [], "related_content": {}}
            
        # 处理提取的页面，传递当前主题
        result = self.extract_vocabulary_and_content(extracted_pages, topic)
        
        # 缓存结果
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
            logger.info(f"已缓存主题 '{topic}' 的处理结果到 {cache_file}")
        except Exception as e:
            logger.warning(f"缓存结果失败: {str(e)}")
            
        return result
    
    def batch_scrape(self, topics, lang="zh"):
        """
        批量处理多个主题
        
        Args:
            topics (list): 主题列表
            lang (str): 语言代码
            
        Returns:
            dict: 综合的处理结果
        """
        combined_results = {
            "vocabulary": [],
            "related_content": {}
        }
        
        logger.info(f"开始处理 {len(topics)} 个主题: {', '.join(topics)}")
        
        # 使用线程池处理多个主题
        with ThreadPoolExecutor(max_workers=min(len(topics), os.cpu_count())) as executor:
            future_to_topic = {executor.submit(self.process_topic, topic, lang): topic for topic in topics}
            
            for future in tqdm(as_completed(future_to_topic), total=len(topics), desc="处理主题"):
                topic = future_to_topic[future]
                try:
                    result = future.result()
                    
                    # 添加主题到词汇表
                    if topic not in combined_results["vocabulary"]:
                        combined_results["vocabulary"].append(topic)
                    
                    # 合并相关内容
                    for category, snippets in result.get("related_content", {}).items():
                        if category not in combined_results["related_content"]:
                            combined_results["related_content"][category] = []
                        combined_results["related_content"][category].extend(snippets)
                        
                    logger.info(f"主题 '{topic}' 处理完成")
                        
                except Exception as e:
                    logger.error(f"处理主题 '{topic}' 时出错: {str(e)}")
        
        # 对每个类别的内容去重和限制数量
        for category in combined_results["related_content"]:
            combined_results["related_content"][category] = list(set(combined_results["related_content"][category]))[:20]  # 每类最多保留20个片段
            
        logger.info(f"完成所有主题处理，共包含 {len(combined_results['vocabulary'])} 个主题")
        return combined_results