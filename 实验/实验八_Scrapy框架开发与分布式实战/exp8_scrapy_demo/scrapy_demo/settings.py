"""
实验八 - Scrapy 项目配置文件
包含爬虫行为、管道、中间件、分布式等全部配置

Settings documentation:
https://docs.scrapy.org/en/latest/topics/settings.html
"""

# ============================================================
# 1. 基本爬虫行为配置
# ============================================================
BOT_NAME = "scrapy_demo"
SPIDER_MODULES = ["scrapy_demo.spiders"]
NEWSPIDER_MODULE = "scrapy_demo.spiders"

# 爬虫协议（遵守 robots.txt）
ROBOTSTXT_OBEY = True

# 并发请求数（单机模式）
CONCURRENT_REQUESTS = 16

# 下载延迟（秒），对目标站点友好的爬取速度
DOWNLOAD_DELAY = 1

# 同一站点并发请求数
CONCURRENT_REQUESTS_PER_DOMAIN = 8

# 禁用 Cookie（除非需要登录态）
COOKIES_ENABLED = False

# 默认请求头
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# ============================================================
# 2. 数据管道配置（ITEM_PIPELINES）
# 数值越小优先级越高（1-1000 范围）
# ============================================================
ITEM_PIPELINES = {
    # JSON 数组格式管道（优先级 300）
    "scrapy_demo.pipelines.JsonFilePipeline": 300,
    # JSON Lines 格式管道（优先级 400）
    "scrapy_demo.pipelines.JsonLinesPipeline": 400,
    # CSV 格式管道（优先级 500）
    "scrapy_demo.pipelines.CsvFilePipeline": 500,
}

# ============================================================
# 3. 下载中间件配置（DOWNLOADER_MIDDLEWARES）
# ============================================================
DOWNLOADER_MIDDLEWARES = {
    # 自定义随机 UA 中间件（优先级 543）
    "scrapy_demo.middlewares.RandomUserAgentMiddleware": 543,
    # 关闭 Scrapy 默认的 UA 中间件
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
}

# ============================================================
# 4. 分布式爬虫配置（scrapy-redis）
# 启用分布式部署时取消以下注释
# 安装: pip install scrapy-redis redis
# ============================================================

# --- 开启 Redis 分布式调度器 ---
# SCHEDULER = "scrapy_redis.scheduler.Scheduler"

# --- 开启 Redis 去重过滤器 ---
# DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"

# --- Redis 连接地址 ---
# REDIS_URL = "redis://127.0.0.1:6379/0"

# --- 爬虫结束后不清空请求队列，支持断点续爬 ---
# SCHEDULER_PERSIST = True

# --- 分布式模式下开启 scrapy-redis 管道 ---
# ITEM_PIPELINES.update({
#     "scrapy_redis.pipelines.RedisPipeline": 400,
# })

# ============================================================
# 5. 日志与调试配置
# ============================================================
LOG_LEVEL = "INFO"
# LOG_FILE = "scrapy.log"  # 日志输出到文件

# ============================================================
# 6. 扩展配置
# ============================================================
# 自动限速（AutoThrottle）
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 5
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

# 重试配置
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# 请求超时
DOWNLOAD_TIMEOUT = 15
