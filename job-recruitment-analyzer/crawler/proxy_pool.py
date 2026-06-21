"""
动态代理池
=========
从免费代理网站获取代理IP → 逐个验证可用性 → 存入队列 → 轮换使用。

白话解释：你家用宽带上网时，你的IP地址是固定的。
如果短时间内几千次请求都来自同一个IP，网站会封掉这个IP。
代理池就是找一批别人的IP替你发请求，天塌了有高个子顶着。

实现逻辑：
  免费代理源 → get_proxies() 抓取 → validate() 测试 → 存入可用队列
  每次请求前 → get_proxy() 取一个 → 用完后标记好坏 → 坏的换掉

🆕 熔断机制：
  每个代理有失败计数器，连续失败2次直接拉黑。
  可用代理 < 3个 → 自动降级为直连模式（配合长延时），不卡死爬虫。
"""
import time
import random
import threading
from collections import deque, defaultdict
from typing import Optional, Dict

import requests
from loguru import logger

from crawler.ua_pool import get_random_ua

# ============================================================
# 免费代理源 URL 列表
# ============================================================
PROXY_SOURCES = [
    "https://ip.ihuan.me/address/5Lit5Zu9.html",
    "https://www.89ip.cn/api/?&tqsl=50&sxa=&sxb=&tta=&ports=&ktip=&cf=1",
    "https://proxy.ip3366.net/free/?action=china&page=1",
    "https://www.kuaidaili.com/free/intr/1/",
]

FALLBACK_PROXIES = []


class ProxyPool:
    """
    代理池类
    -------
    维护一个可用代理队列，支持：
    1. 自动从免费源获取新代理
    2. 验证代理可用性
    3. 轮换使用，坏代理自动淘汰
    4. 🔥 连续失败2次自动熔断拉黑
    5. 🔥 可用<3个自动降级直连模式
    6. 线程安全

    用法：
        pool = ProxyPool(min_size=5)
        pool.refresh()
        proxy = pool.get()
        pool.report(proxy, ok=True)
    """

    def __init__(self, min_size: int = 5):
        self.min_size = min_size
        self._pool: deque = deque()                          # 代理队列
        self._bad_proxies: set = set()                       # 永久黑名单
        self._fail_count: Dict[str, int] = defaultdict(int)  # 🔥 每个代理的连续失败次数
        self._lock = threading.Lock()
        self._total_validated = 0
        self._degraded = False                               # 🔥 是否已降级为直连模式

    # ---- 获取原始代理列表 ----

    def _fetch_from_source(self, url: str) -> list:
        """从单个代理源抓取代理列表"""
        proxies = []
        try:
            headers = {"User-Agent": get_random_ua()}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return proxies
            text = resp.text
            import re
            matches = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5})', text)
            for match in matches:
                http_proxy = f"http://{match}"
                proxies.append({"http": http_proxy, "https": http_proxy})
        except Exception as e:
            logger.debug(f"代理源 {url[:50]}... 获取失败: {e}")
        return proxies

    def _fetch_all_raw(self) -> list:
        """从所有代理源获取原始代理列表，去重"""
        all_proxies = []
        seen = set()
        for url in PROXY_SOURCES:
            raw = self._fetch_from_source(url)
            for p in raw:
                key = p["http"]
                if key not in seen:
                    seen.add(key)
                    all_proxies.append(p)
            time.sleep(0.5)
        logger.info(f"从 {len(PROXY_SOURCES)} 个源获取到 {len(all_proxies)} 个原始代理")
        return all_proxies

    # ---- 验证代理 ----

    def _validate_proxy(self, proxy: Dict[str, str], timeout: int = 5) -> bool:
        """测试代理是否可用（访问百度）"""
        test_urls = ["http://www.baidu.com", "https://www.baidu.com"]
        for url in test_urls:
            try:
                resp = requests.get(
                    url, proxies=proxy,
                    headers={"User-Agent": get_random_ua()},
                    timeout=timeout,
                )
                if resp.status_code == 200 and "百度" in resp.text[:500]:
                    return True
            except Exception:
                continue
        return False

    # ---- 刷新代理池 ----

    def refresh(self) -> int:
        """刷新代理池：获取→验证→加入队列"""
        raw_proxies = self._fetch_all_raw()
        if not raw_proxies:
            raw_proxies = FALLBACK_PROXIES
            logger.warning("所有代理源获取失败，使用兜底代理")

        new_count = 0
        for proxy in raw_proxies:
            if len(self._pool) >= self.min_size * 3:
                break
            if proxy["http"] in self._bad_proxies:
                continue
            if self._validate_proxy(proxy):
                with self._lock:
                    self._pool.append(proxy)
                new_count += 1
                self._total_validated += 1
                self._fail_count[proxy["http"]] = 0  # 🔥 重置失败计数
                logger.debug(f"✅ 代理可用: {proxy['http']}")

        logger.info(f"代理池刷新完成: {new_count} 个新代理，池中共 {len(self._pool)} 个")

        # 🔥 判断是否需要降级
        self._check_degradation()
        return new_count

    # ---- 🔥 自动降级判断 ----

    def _check_degradation(self):
        """检查是否要降级为直连模式"""
        if len(self._pool) < 3 and not self._degraded:
            self._degraded = True
            logger.warning(
                f"⚠️ 可用代理仅剩 {len(self._pool)} 个（< 3），自动降级为直连模式。"
                f"直连时延时加倍，确保反爬安全。"
            )
        elif len(self._pool) >= 3 and self._degraded:
            self._degraded = False
            logger.info("✅ 代理池恢复（≥3个），切回代理模式")

    def should_use_direct(self) -> bool:
        """
        调用方判断是否应走直连模式

        当代理池可用数 < 3 时返回 True，
        爬虫收到 True 后会自动走直连 + 长延时。
        """
        return self._degraded or len(self._pool) < 3

    # ---- 获取/归还代理 ----

    def get(self) -> Optional[Dict[str, str]]:
        """从池中取出一个代理（轮换模式），池空返回 None"""
        with self._lock:
            if self._pool:
                proxy = self._pool.popleft()
                self._pool.append(proxy)
                return proxy
        return None

    def report(self, proxy: Dict[str, str], ok: bool):
        """
        报告代理使用结果

        🔥 新增熔断逻辑：
        - 失败时累加计数
        - 连续失败 ≥ 2 次 → 直接拉黑 + 移出队列
        - 成功时重置计数
        - 之后检查是否需要降级
        """
        if proxy is None:
            return

        key = proxy["http"]

        with self._lock:
            if not ok:
                # 累加失败次数
                self._fail_count[key] += 1
                fail_cnt = self._fail_count[key]

                if fail_cnt >= 2:
                    # 🔥 连续失败2次 → 熔断拉黑
                    self._bad_proxies.add(key)
                    self._fail_count.pop(key, None)
                    try:
                        self._pool.remove(proxy)
                    except ValueError:
                        pass
                    logger.warning(f"🔥 代理熔断: {key}（连续失败 {fail_cnt} 次，永久拉黑）")
                else:
                    # 第一次失败，标记但不移除（可能是偶发故障）
                    logger.debug(f"⚠️ 代理异常 ({fail_cnt}/2): {key}")
            else:
                # 成功 → 重置失败计数
                self._fail_count[key] = 0

        # 🔥 每次报告后检查降级状态
        self._check_degradation()

    def count(self) -> int:
        """当前可用代理数"""
        return len(self._pool)

    def stats(self) -> dict:
        """返回池子统计信息"""
        return {
            "available": len(self._pool),
            "bad": len(self._bad_proxies),
            "total_validated": self._total_validated,
            "degraded": self._degraded,
            "fail_tracking": dict(self._fail_count),
        }


# 全局单例
proxy_pool = ProxyPool(min_size=5)
