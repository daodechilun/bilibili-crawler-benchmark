"""
实验八 - 下载中间件
实现随机 User-Agent 中间件，规避基础反爬拦截
"""
import random


class RandomUserAgentMiddleware:
    """
    随机 UA 下载中间件
    每次请求从 UA 池中随机选取一个 User-Agent，
    模拟不同浏览器访问，规避基于 UA 的基础反爬机制
    """

    # 多浏览器 UA 池（覆盖 Chrome、Firefox、Edge、Safari）
    USER_AGENT_LIST = [
        # Chrome on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Chrome on Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        # Firefox on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) "
        "Gecko/20100101 Firefox/119.0",
        # Edge on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        # Safari on Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        # Chrome on Linux
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Chrome on Android
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    ]

    def process_request(self, request, spider):
        """
        拦截每个请求，随机设置 User-Agent 请求头
        此方法在请求发送前由 Scrapy 引擎自动调用
        """
        ua = random.choice(self.USER_AGENT_LIST)
        request.headers['User-Agent'] = ua
        spider.logger.debug(f"[RandomUA] 使用 UA: {ua[:60]}...")
