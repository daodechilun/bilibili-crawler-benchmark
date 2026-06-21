"""
爬虫模块 (crawler)
=================
负责从51job采集IT岗位数据。

包含：
  - live_spider.py → 主力爬虫（Selenium + 浏览器内 fetch + 反检测）
  - ua_pool.py     → User-Agent轮换池（20+浏览器标识）
  - proxy_pool.py  → 动态代理池（获取→验证→轮换→熔断→降级）
  - cookie_mgr.py  → Cookie/Session管理（维持登录态）
  - archived/      → 废弃方案归档（requests/stealth/manual等实验代码）
"""
from crawler.live_spider import LiveSpider
from crawler.ua_pool import UAPool, get_random_ua, ua_pool
from crawler.proxy_pool import ProxyPool, proxy_pool
from crawler.cookie_mgr import CookieManager, cookie_mgr

__all__ = [
    "LiveSpider", "UAPool", "get_random_ua", "ua_pool",
    "ProxyPool", "proxy_pool", "CookieManager", "cookie_mgr",
]
