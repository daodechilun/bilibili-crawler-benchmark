"""
全局配置文件
============
所有模块的公共参数都在这里，改一处全项目生效。
你不需要去每个文件里翻参数，改这里就行。
"""
import os

# ============================================================
# 项目路径
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
CLEANED_DIR = os.path.join(DATA_DIR, "cleaned")
LOG_DIR = os.path.join(BASE_DIR, "logs")
STATIC_DIR = os.path.join(BASE_DIR, "visualization", "static")
CHART_DIR = os.path.join(STATIC_DIR, "charts")

# 确保目录存在
for d in [RAW_DIR, CLEANED_DIR, LOG_DIR, CHART_DIR]:
    os.makedirs(d, exist_ok=True)

# ============================================================
# 爬虫配置
# ============================================================

# 搜索关键词（4个岗位方向）
KEYWORDS = [
    "数据分析",
    "Python开发",
    "AI算法",
    "大数据开发",
]

# 目标城市（中文名 → 51job城市代码，用于后续清洗过滤）
TARGET_CITIES = [
    "北京", "上海", "广州", "深圳",
    "杭州", "成都", "武汉", "南京", "西安", "长沙",
]

# 城市层级映射（用于清洗阶段标注 city_tier）
CITY_TIER = {
    "北京": "一线", "上海": "一线", "广州": "一线", "深圳": "一线",
    "杭州": "新一线", "成都": "新一线", "武汉": "新一线",
    "南京": "新一线", "西安": "新一线", "长沙": "新一线",
}

# 每个关键词采集条数（取前 N 条）
JOBS_PER_KEYWORD = 800

# 每页条数（51job API 最大支持 50）
PAGE_SIZE = 50

# 最大翻页数（800 ÷ 50 = 16 页/关键词）
MAX_PAGES = JOBS_PER_KEYWORD // PAGE_SIZE

# ============================================================
# 反爬参数
# ============================================================

# 随机延时范围（秒）—— 模拟人类浏览速度
DELAY_MIN = 3.0
DELAY_MAX = 8.0

# 详情页延时（秒）—— 稍微温柔点，因为请求量翻倍
DETAIL_DELAY_MIN = 3.0
DETAIL_DELAY_MAX = 6.0

# 最大重试次数
MAX_RETRIES = 3

# 重试间隔（秒）—— 指数退避：wait * (2 ** retry_count)
RETRY_BASE_WAIT = 5.0

# 代理池最少可用 IP 数量
MIN_PROXY_COUNT = 5

# User-Agent 池大小
UA_POOL_SIZE = 20

# 遇到验证码时的暂停时间（秒）
CAPTCHA_PAUSE = 120

# ============================================================
# 51job API 端点
# ============================================================

# 搜索 API（新版，返回 JSON）
API_SEARCH_URL = "https://we.51job.com/api/job/search-pc"

# 详情 API
API_DETAIL_URL = "https://we.51job.com/api/job/detail"

# 通用请求头模板
HEADERS_TEMPLATE = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

# ============================================================
# 数据库配置（MySQL）
# ============================================================

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "job_analysis",
    "charset": "utf8mb4",
}

# ============================================================
# Flask 配置
# ============================================================

FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5000
FLASK_DEBUG = True

# ============================================================
# ML 模型参数
# ============================================================

# 薪资预测：随机森林参数
RF_PARAMS = {
    "n_estimators": 200,
    "max_depth": 15,
    "min_samples_split": 5,
    "random_state": 42,
    "n_jobs": -1,
}

# XGBoost 参数
XGB_PARAMS = {
    "n_estimators": 200,
    "max_depth": 6,
    "learning_rate": 0.1,
    "random_state": 42,
    "n_jobs": -1,
}

# KMeans：K 值搜索范围
KMEANS_K_RANGE = range(2, 10)

# 技能向量 TF-IDF 最大特征数（技能词典~60词，设100留余量）
TFIDF_MAX_FEATURES = 100

# ============================================================
# 城市→省份映射（ECharts中国地图用）
# ============================================================
CITY_TO_PROVINCE = {
    "北京": "北京", "上海": "上海", "天津": "天津", "重庆": "重庆",
    "深圳": "广东", "广州": "广东", "东莞": "广东", "佛山": "广东",
    "杭州": "浙江", "宁波": "浙江", "温州": "浙江",
    "南京": "江苏", "苏州": "江苏", "无锡": "江苏", "常州": "江苏",
    "成都": "四川", "绵阳": "四川",
    "武汉": "湖北", "宜昌": "湖北",
    "西安": "陕西",
    "长沙": "湖南",
    "珠海": "广东", "肇庆": "广东", "湛江": "广东",
    "郑州": "河南", "洛阳": "河南",
    "合肥": "安徽",
    "福州": "福建", "厦门": "福建",
    "青岛": "山东", "济南": "山东", "烟台": "山东",
    "大连": "辽宁", "沈阳": "辽宁",
    "昆明": "云南",
    "贵阳": "贵州",
    "石家庄": "河北",
    "哈尔滨": "黑龙江",
    "长春": "吉林",
    "太原": "山西",
    "南昌": "江西",
    "南宁": "广西",
    "海口": "海南",
    "拉萨": "西藏",
    "乌鲁木齐": "新疆",
    "呼和浩特": "内蒙古",
    "银川": "宁夏",
    "西宁": "青海",
    "兰州": "甘肃",
}
