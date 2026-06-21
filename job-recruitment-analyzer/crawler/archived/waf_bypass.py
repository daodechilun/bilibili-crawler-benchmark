"""
51job WAF 绕过模块
=================
阿里云WAF需要浏览器执行JavaScript才能通过验证。

策略（3层）：
  第1层: Selenium + undetected-chrome 启动"看起来像真人的浏览器"
  第2层: 访问51job首页让浏览器自然执行JS通过WAF
  第3层: 提取Cookie→交给requests调API（比Selenium快10倍）

如果undetected-chromedriver不可用，退回到标准Selenium + 反检测参数。
"""
import time
import os
import json
import tempfile
from typing import Optional, Dict

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from loguru import logger


class WAFBypass:
    """
    WAF 绕过器
    ----------
    打开一个"真人浏览器"→访问51job→过WAF→导出Cookie给requests用。

    用法:
        bypass = WAFBypass()
        cookies = bypass.get_cookies()   # 拿到能过WAF的Cookie字典
        bypass.quit()                     # 用完关浏览器
    """

    def __init__(self, headless: bool = False):
        """
        参数:
            headless: True=无头模式（后台运行），False=有头（能看到浏览器操作）
                     建议先用有头模式确认能过WAF，再切无头
        """
        self.driver = None
        self.headless = headless
        self._cookies = None

    def _build_chrome_options(self) -> Options:
        """
        构造Chrome启动参数

        关键反检测措施:
        - CDP注入隐藏webdriver标记
        - 禁用automation特征
        - 伪装成普通Chrome窗口
        """
        opts = Options()

        if self.headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1366,768")
        opts.add_argument("--lang=zh-CN")

        # 隐藏自动化标记
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)

        # 伪装UA
        opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        return opts

    def launch(self) -> bool:
        """
        启动浏览器并访问51job首页，等待WAF验证通过

        返回: True=成功加载（WAF已过）, False=失败
        """
        logger.info("Launching Chrome browser (standard Selenium + anti-detection)...")

        try:
            opts = self._build_chrome_options()

            # 尝试多种driver初始化方式（应对不同的网络/环境情况）
            driver_started = False
            last_error = None

            # 方式1: webdriver-manager（自动下载匹配的driver，缓存到本地）
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.chrome.service import Service as ChromeService
                service = ChromeService(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=opts)
                driver_started = True
                logger.info("   Driver: webdriver-manager OK")
            except Exception as e:
                last_error = e
                logger.debug(f"   webdriver-manager failed: {e}")

            # 方式2: Selenium自带管理器
            if not driver_started:
                try:
                    self.driver = webdriver.Chrome(options=opts)
                    driver_started = True
                    logger.info("   Driver: Selenium auto-manager OK")
                except Exception as e:
                    last_error = e
                    logger.debug(f"   Selenium auto-manager failed: {e}")

            if not driver_started:
                raise RuntimeError(f"All Chrome driver methods failed. Last error: {last_error}")

            # 注入JS隐藏webdriver痕迹
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN','zh','en']});
                    window.chrome = {runtime: {}};
                """}
            )

            # 访问51job首页
            logger.info("   Navigating to https://www.51job.com/ ...")
            self.driver.get("https://www.51job.com/")

            # 等待页面完全加载（JS执行完≈WAF验证通过）
            time.sleep(8)

            # 检查是否真的加载成功了
            page_source = self.driver.page_source
            if "aliyun_waf" in page_source.lower():
                logger.warning("   WAF challenge detected, waiting for JS to solve...")
                # WAF出现了，等它自己解（通常3-8秒）
                time.sleep(12)
                page_source = self.driver.page_source
                if "aliyun_waf" in page_source.lower():
                    logger.error("   WAF still present after wait!")
                    return False

            logger.info(f"   Page loaded: {len(page_source)} chars")
            logger.info(f"   Current URL: {self.driver.current_url[:80]}")

            # 提取Cookie
            self._cookies = {}
            for cookie in self.driver.get_cookies():
                self._cookies[cookie["name"]] = cookie["value"]

            logger.info(f"   Got {len(self._cookies)} cookies: {list(self._cookies.keys())}")
            return True

        except Exception as e:
            logger.error(f"   Browser launch failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_cookies(self) -> Dict[str, str]:
        """获取当前Cookie字典（给requests用）"""
        if self._cookies is None:
            # 尝试从driver直接获取
            if self.driver:
                self._cookies = {}
                for c in self.driver.get_cookies():
                    self._cookies[c["name"]] = c["value"]
        return self._cookies or {}

    def refresh_cookies(self) -> bool:
        """
        刷新Cookie（当requests请求开始被WAF拦截时调用）

        在浏览器里随便点几个页面，让WAF觉得这是真人在浏览。
        """
        if not self.driver:
            return False
        try:
            logger.info("   Refreshing cookies...")
            # 模拟真人：随便点几个链接
            self.driver.get("https://www.51job.com/")
            time.sleep(3)
            # 尝试点搜索框（如果有的话）
            try:
                search_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='text']")
                search_input.click()
                time.sleep(1)
                search_input.send_keys("Python")
                time.sleep(2)
            except Exception:
                pass

            self._cookies = {}
            for c in self.driver.get_cookies():
                self._cookies[c["name"]] = c["value"]
            logger.info(f"   Got {len(self._cookies)} refreshed cookies")
            return True
        except Exception as e:
            logger.error(f"   Cookie refresh failed: {e}")
            return False

    def test_api(self) -> bool:
        """
        用Selenium的浏览器直接发API请求测试是否过WAF

        方法：在浏览器console里用fetch调API，
              或者直接用driver.get请求API URL看返回什么。
        """
        if not self.driver:
            return False

        logger.info("   Testing API access via browser...")
        api_url = "https://we.51job.com/api/job/search-pc?api_key=51job&keyword=Python&searchType=2&jobArea=000000&pageNum=1&pageSize=5&source=1"
        self.driver.get(api_url)
        time.sleep(3)

        # 检查返回内容
        body = self.driver.find_element(By.TAG_NAME, "body").text
        if "aliyun_waf" in body.lower() or "waf" in body.lower():
            logger.warning("   API still blocked by WAF via browser!")
            return False

        # 尝试解析JSON
        try:
            # 浏览器显示的可能是原始JSON
            import json
            data = json.loads(body)
            result = data.get("engine_search_result") or data.get("resultbody")
            if result:
                if isinstance(result, list):
                    logger.info(f"   API accessible! Got {len(result)} results")
                elif isinstance(result, dict):
                    job = result.get("job", {})
                    items = job.get("items", []) if isinstance(job, dict) else []
                    logger.info(f"   API accessible! Got {len(items)} results via resultbody.job.items")
                return True
        except (json.JSONDecodeError, ValueError):
            pass

        logger.info(f"   Response starts with: {body[:200]}")
        return "job" in body.lower() or "engine_search_result" in body.lower()

    def quit(self):
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
            logger.info("   Browser closed")


# ================================================================
# 测试入口
# ================================================================
if __name__ == "__main__":
    bypass = WAFBypass(headless=False)
    try:
        if bypass.launch():
            print("\n--- Testing API ---")
            if bypass.test_api():
                print("\n[SUCCESS] WAF bypass working!")
                cookies = bypass.get_cookies()
                print(f"Cookies: {json.dumps(cookies, indent=2, ensure_ascii=False)}")
            else:
                print("\n[FAIL] API still blocked")
    finally:
        input("\nPress Enter to close browser...")
        bypass.quit()
