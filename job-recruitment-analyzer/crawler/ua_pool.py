"""
User-Agent 池
=============
维护一个 UA 列表，每次请求随机取一个。
模拟不同浏览器/系统访问，降低被封风险。

白话解释：你每次访问网站，网站都能看到你是用什么浏览器。
如果几千次请求都用同一个浏览器标识，一看就是爬虫。
我们准备20多个不同的浏览器标识，每次随机换，像真人访问。
"""
import random
from fake_useragent import UserAgent

# 预定义一批真实常见的 UA（fake-useragent 库偶尔连不上，这是兜底）
FALLBACK_UA_LIST = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0",
    # Firefox on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Safari on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Mobile (模拟手机浏览，有些网站对移动端限制更少)
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
    # 更多 Chrome 版本
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    # 更多 Firefox 版本
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:117.0) Gecko/20100101 Firefox/117.0",
    # Opera
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0",
]


class UAPool:
    """
    UA 池类
    ------
    两种方式生成 UA：
    1. 用 fake_useragent 库动态生成（最新、最真实）
    2. 用预定义的 FALLBACK_UA_LIST（库挂了也不怕）

    用法：
        pool = UAPool()
        ua = pool.random()  # 拿一个随机UA
    """

    def __init__(self):
        """初始化：优先用 fake_useragent，失败就用兜底列表"""
        try:
            # 尝试用 fake_useragent 生成 UA
            self._ua_gen = UserAgent(browsers=["chrome", "firefox", "edge", "safari"])
            self._use_fallback = False
            print("[UA] fake_useragent 库加载成功，动态生成UA")
        except Exception:
            # 如果 fake_useragent 网络请求失败，用预定义的兜底列表
            self._ua_gen = None
            self._use_fallback = True
            print("[UA] WARNING: fake_useragent 不可用，使用预定义UA列表")

    def random(self) -> str:
        """
        返回一个随机 User-Agent 字符串

        每次爬虫发起请求前调用这个函数，拿到一个随机的浏览器标识，
        网站看到的每次请求都像是来自不同的人，降低被封概率。
        """
        if self._use_fallback or self._ua_gen is None:
            return random.choice(FALLBACK_UA_LIST)

        try:
            return self._ua_gen.random
        except Exception:
            return random.choice(FALLBACK_UA_LIST)

    def get_all(self) -> list:
        """返回所有可用的 UA（用于调试）"""
        if self._use_fallback:
            return FALLBACK_UA_LIST.copy()
        return [self.random() for _ in range(20)]  # 生成20个


# 创建全局单例 —— 全项目共用一个 UA 池，避免重复初始化
ua_pool = UAPool()


# 便捷函数：直接拿一个随机 UA
def get_random_ua() -> str:
    return ua_pool.random()
