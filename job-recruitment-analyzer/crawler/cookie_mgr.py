"""
Cookie / Session 管理器
=======================
维持登录态、请求上下文，处理 Cookie 失效自动重登。

白话解释：你访问一个网站，网站会在你浏览器里放一个"小纸条"（Cookie），
上面写着"这个人是XX"。后续请求带着这个小纸条，网站才知道"哦这是刚才那个人"。
我们模拟这个过程：先访问51job首页拿Cookie，然后全程带着这个Cookie发请求。
如果网站返回"需要登录"，说明Cookie失效了，重新拿一次。
"""
import time
import requests
from loguru import logger

from crawler.ua_pool import get_random_ua
import config


class CookieManager:
    """
    Cookie 管理器
    ------------
    封装一个 requests.Session 对象，负责：
    1. 首次访问首页获取初始 Cookie
    2. 每次请求自动携带 Cookie
    3. 检测 Cookie 失效并自动刷新
    4. 维持合理的请求头

    用法：
        mgr = CookieManager()
        session = mgr.get_session()  # 拿到一个带Cookie的会话对象
        resp = session.get(url)      # 用会话发请求（自动带Cookie）
    """

    def __init__(self):
        self._session: requests.Session = None
        self._created_at = 0.0
        self._max_age = 3600  # Cookie 最长存活 1 小时，超时自动刷新

    def get_session(self) -> requests.Session:
        """
        获取一个可用的 Session（带有效 Cookie）

        如果 Session 还没创建，或者距离创建超过 1 小时，
        重新初始化一个。确保 Cookie 始终是新鲜的。
        """
        if self._session is None or self._is_expired():
            self._init_session()
        return self._session

    def _init_session(self):
        """初始化 Session：访问51job首页，拿 Cookie"""
        self._session = requests.Session()

        # 设置基础请求头（假装是正常浏览器）
        ua = get_random_ua()
        self._session.headers.update({
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })

        try:
            # 访问51job首页，让服务器给我们设置 Cookie
            resp = self._session.get(
                "https://www.51job.com/",
                timeout=15,
                allow_redirects=True,
            )
            self._created_at = time.time()
            cookie_count = len(self._session.cookies)
            logger.info(f"✅ Cookie 初始化成功，获取到 {cookie_count} 个 Cookie")
        except Exception as e:
            logger.warning(f"⚠️ Cookie 初始化失败: {e}，使用空 Cookie 继续")
            self._created_at = time.time()

    def refresh(self):
        """强制刷新 Cookie（在检测到失效时调用）"""
        logger.info("🔄 强制刷新 Cookie...")
        self._init_session()

    def _is_expired(self) -> bool:
        """判断 Cookie 是否过期（超过1小时）"""
        return (time.time() - self._created_at) > self._max_age

    def get_cookies_dict(self) -> dict:
        """返回当前 Cookie 的字典形式（给 Selenium 用）"""
        session = self.get_session()
        return requests.utils.dict_from_cookiejar(session.cookies)


# 全局单例
cookie_mgr = CookieManager()
