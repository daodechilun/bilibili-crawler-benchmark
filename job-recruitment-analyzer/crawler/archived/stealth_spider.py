"""
超强反检测爬虫 ⚡
================
三层策略：
  1. selenium-stealth 全面伪装（7个检测点）
  2. 浏览器内部fetch()调API（不暴露Python痕迹）
  3. 如遇滑块→提示用户手动拖一次→Cookie生效后自动继续

为什么用fetch()而不是requests？
  requests从Python发出去的请求没有浏览器的WAF Cookie，
  即使Selenium拿到了Cookie，requests的TLS指纹也不一样。
  但在浏览器里用fetch()发请求，WAF看到的就是正常的AJAX请求。

用法：
  py -3.10 crawler/stealth_spider.py
  → 浏览器弹出 → 如果看到滑块就拖一下 → 回车继续 → 自动采集
"""
import time
import random
import json
import csv
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium_stealth import stealth

from loguru import logger

import config

# 字段定义
FIELDNAMES = [
    "job_title", "salary_text", "salary_min", "salary_max", "salary_avg",
    "city", "district", "education", "experience",
    "company_name", "company_size", "industry",
    "skill_tags", "publish_date", "job_url",
    "keyword", "crawl_time",
]


class StealthSpider:
    """超强反检测爬虫"""

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.driver = None
        self.results = []
        self.csv_path = os.path.join(config.RAW_DIR, "raw_data.csv")
        self.checkpoint_path = os.path.join(config.LOG_DIR, "stealth_checkpoint.json")

    # ================================================================
    # 浏览器启动（核心反检测）
    # ================================================================

    def _launch(self):
        """启动伪装浏览器"""
        logger.info("[LAUNCH] Starting stealth Chrome...")

        opts = Options()
        if self.headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1366,800")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)

        self.driver = webdriver.Chrome(options=opts)

        # 🔥 selenium-stealth 全面反检测（覆盖7个检测点）
        stealth(
            self.driver,
            languages=["zh-CN", "zh"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )
        logger.info("   Stealth applied (7 detection points patched)")

        return self

    # ================================================================
    # Cookie 预热
    # ================================================================

    def _warmup(self):
        """
        访问首页建立Cookie信任链

        先访问www.51job.com（无反爬），
        再访问we.51job.com（API域名），
        让WAF看到同一个浏览器在两个域名间自然跳转。
        """
        logger.info("[WARMUP] Building cookie trust...")

        # Step 1: 访问51job首页
        self.driver.get("https://www.51job.com/")
        time.sleep(4)
        logger.info(f"   Homepage: {len(self.driver.page_source)} chars")

        # Step 2: 随意点击/滚动（模拟真人行为）
        self.driver.execute_script("window.scrollTo(0, 500)")
        time.sleep(1.5)
        self.driver.execute_script("window.scrollTo(0, 200)")
        time.sleep(1)

        # Step 3: 检查是否有acw_tc（阿里云WAF通行证）
        cookies = self.driver.get_cookies()
        cookie_names = [c["name"] for c in cookies]
        has_waf_cookie = any("acw" in n or "waf" in n.lower() for n in cookie_names)
        logger.info(f"   Cookies: {cookie_names}")
        logger.info(f"   WAF cookie present: {has_waf_cookie}")

    # ================================================================
    # 🔥 核心：浏览器内部fetch()调用API
    # ================================================================

    def _fetch_api_page(self, keyword: str, page: int) -> Optional[List[Dict]]:
        """
        在浏览器里执行fetch()调51job搜索API

        为什么这比Python requests安全？
        - 请求从真实浏览器发出，TLS指纹正常
        - 自动携带所有Cookie（包括WAF通行证）
        - 请求头和浏览器完全一致
        - WAF看到的就是一次正常的AJAX翻页

        返回：职位dict列表，失败返回None
        """
        params = {
            "api_key": "51job",
            "keyword": keyword,
            "searchType": "2",
            "jobArea": "000000",
            "pageNum": page,
            "pageSize": 50,
            "source": "1",
            "sortType": "0",
        }
        # 构建query string
        qs = "&".join(f"{k}={v}" for k, v in params.items())

        keyword_quoted = quote(keyword)
        js_code = f"""
        async function fetchJobs() {{
            try {{
                const url = 'https://we.51job.com/api/job/search-pc?' + '{qs}';
                const resp = await fetch(url, {{
                    method: 'GET',
                    credentials: 'include',
                    headers: {{
                        'Accept': 'application/json',
                        'Referer': 'https://we.51job.com/pc/search?keyword={keyword_quoted}',
                    }}
                }});
                const text = await resp.text();
                return text;
            }} catch(e) {{
                return 'ERROR:' + e.message;
            }}
        }}
        return await fetchJobs();
        """

        try:
            raw = self.driver.execute_script(js_code)
            if not raw or raw.startswith("ERROR:"):
                logger.warning(f"   fetch() failed: {raw}")
                return None

            # 检查是否被WAF拦截
            if "aliyun_waf" in raw.lower() or "滑块" in raw or len(raw) < 200:
                logger.warning(f"   WAF block in fetch() response ({len(raw)} chars)")
                logger.warning(f"   WAF preview: {raw[:600]}")
                return None

            data = json.loads(raw)

            # 提取职位列表（兼容多种JSON结构）
            items = None
            result = data.get("engine_search_result") or data.get("resultbody")
            if isinstance(result, list):
                items = result
            elif isinstance(result, dict):
                job = result.get("job")
                if isinstance(job, dict):
                    items = job.get("items") or job.get("list")
                if not items:
                    items = result.get("items") or result.get("list") or result.get("data")
            if not items:
                for key in ["list", "data", "items", "jobs"]:
                    val = data.get(key)
                    if isinstance(val, list):
                        items = val
                        break

            if not items:
                logger.debug(f"   No job list found in response. Keys: {list(data.keys())[:5]}")
                return []

            # 解析每条职位
            parsed = []
            for item in items:
                try:
                    job = self._parse_item(item, keyword)
                    if job and job.get("job_title"):
                        parsed.append(job)
                except Exception:
                    continue

            return parsed

        except json.JSONDecodeError as e:
            logger.warning(f"   JSON parse error: {e}")
            return None
        except Exception as e:
            logger.error(f"   fetch() exception: {e}")
            return None

    def _parse_item(self, item: dict, keyword: str) -> Dict:
        """将API返回的单条职位转为标准格式"""
        job_title = item.get("jobName") or item.get("job_name") or ""

        salary_text = item.get("providesalary") or item.get("salary") or ""
        workarea = item.get("workarea") or item.get("city") or ""
        education = item.get("degreefrom") or item.get("education") or ""
        experience = item.get("workyear") or item.get("workingExp") or ""

        # 城市标准化
        city = workarea
        district = ""
        if workarea and len(workarea) > 2:
            # 简单处理："北京朝阳区"→ city=北京
            from parser.salary_parser import normalize_city
            city, district = normalize_city(workarea)

        # 技能标签
        skill_tags_raw = item.get("attribute") or []
        if isinstance(skill_tags_raw, list):
            skill_tags = ", ".join(skill_tags_raw)
        else:
            skill_tags = str(skill_tags_raw)

        # 经验数值化
        from parser.salary_parser import parse_experience
        exp_min, exp_max = parse_experience(experience)

        return {
            "job_title": job_title,
            "salary_text": salary_text,
            "salary_min": None, "salary_max": None, "salary_avg": None,
            "city": city,
            "district": district,
            "education": education,
            "experience": experience,
            "exp_min": exp_min,
            "exp_max": exp_max,
            "company_name": item.get("companyName") or item.get("company_name") or "",
            "company_size": item.get("companySize") or item.get("companysize") or "",
            "industry": item.get("companyind_text") or item.get("industry") or "",
            "skill_tags": skill_tags,
            "publish_date": item.get("issuedate") or "",
            "job_url": f"https://jobs.51job.com/all/{item.get('jobId','')}.html",
            "keyword": keyword,
            "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    # ================================================================
    # 搜索入口
    # ================================================================

    def search(self, keyword: str, max_pages: int = None) -> List[Dict]:
        """
        搜索一个关键词

        流程：
        1. 对于每一页，在浏览器里用fetch()调API
        2. 成功→解析→下一页
        3. 遇到WAF→提示用户手动过滑块→重试
        """
        if max_pages is None:
            max_pages = config.MAX_PAGES

        results = []
        logger.info(f"[SEARCH] {keyword} (max {max_pages} pages)")

        # 加载断点
        cp = self._load_checkpoint()
        start_page = 1
        if cp and cp.get("current_keyword") == keyword:
            start_page = cp.get("current_page", 1) + 1
            logger.info(f"   Resume from page {start_page}")

        consecutive_fails = 0

        for page in range(start_page, max_pages + 1):
            logger.info(f"   Page {page}/{max_pages}...")

            # 随机延时（模拟人类翻页速度）
            time.sleep(random.uniform(config.DELAY_MIN, config.DELAY_MAX))

            items = self._fetch_api_page(keyword, page)

            if items is None:
                consecutive_fails += 1
                logger.warning(f"   Page {page} failed ({consecutive_fails}/3)")

                if consecutive_fails >= 3:
                    # 🔥 可能是WAF升级了，提示用户手动处理
                    logger.warning("=" * 50)
                    logger.warning("3 consecutive failures detected!")
                    logger.warning("Please manually navigate to the search page and solve any captcha.")
                    logger.warning("=" * 50)

                    # 在浏览器里打开搜索页，让用户手动操作
                    search_url = f"https://we.51job.com/pc/search?keyword={quote(keyword)}&pageNum={page}"
                    self.driver.get(search_url)

                    input(f"\n>>> Please solve any captcha in the browser, then press Enter here to continue...")

                    # 重试当前页
                    consecutive_fails = 0
                    time.sleep(3)
                    items = self._fetch_api_page(keyword, page)

                if items is None:
                    self._save_checkpoint(keyword, page)
                    continue

            consecutive_fails = 0

            if len(items) == 0:
                logger.info("   No more results")
                break

            results.extend(items)
            self._save_checkpoint(keyword, page)
            logger.info(f"   Got {len(items)} jobs, total {len(results)}")

            if len(results) >= config.JOBS_PER_KEYWORD:
                logger.info(f"   Target reached: {config.JOBS_PER_KEYWORD}")
                break

        self._save_checkpoint(keyword, max_pages, finished=True)
        return results

    # ================================================================
    # 断点 / 存储
    # ================================================================

    def _save_checkpoint(self, keyword, page, finished=False):
        cp = {"current_keyword": keyword, "current_page": page, "finished": finished}
        try:
            with open(self.checkpoint_path, "w") as f:
                json.dump(cp, f)
        except Exception:
            pass

    def _load_checkpoint(self):
        if not os.path.exists(self.checkpoint_path):
            return None
        try:
            with open(self.checkpoint_path) as f:
                return json.load(f)
        except Exception:
            return None

    def save_csv(self):
        if not self.results:
            return
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        with open(self.csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self.results)
        logger.info(f"[SAVE] {len(self.results)} records -> {self.csv_path}")

    # ================================================================
    # 主入口
    # ================================================================

    def run(self, keywords=None):
        if keywords is None:
            keywords = config.KEYWORDS

        logger.info("=" * 60)
        logger.info(" STEALTH SPIDER - 51job Job Data Collector")
        logger.info(f" Keywords: {keywords}")
        logger.info("=" * 60)

        try:
            self._launch()
            self._warmup()

            for kw in keywords:
                logger.info(f"\n--- Keyword: {kw} ---")
                results = self.search(kw)
                self.results.extend(results)
                self.save_csv()
                logger.info(f"Total so far: {len(self.results)}")

            self._print_summary()

        except KeyboardInterrupt:
            logger.info("Interrupted. Saving progress...")
            self.save_csv()
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("Browser closed")

        return self.results

    def _print_summary(self):
        if not self.results:
            logger.warning("NO DATA COLLECTED")
            return
        kw_counts = {}
        for r in self.results:
            kw = r.get("keyword", "?")
            kw_counts[kw] = kw_counts.get(kw, 0) + 1
        logger.info(f"\n{'='*40}")
        logger.info(f"TOTAL: {len(self.results)} jobs")
        for kw, cnt in sorted(kw_counts.items()):
            logger.info(f"  {kw}: {cnt}")
        logger.info(f"CSV: {self.csv_path}")


if __name__ == "__main__":
    spider = StealthSpider(headless=False)
    spider.run()
