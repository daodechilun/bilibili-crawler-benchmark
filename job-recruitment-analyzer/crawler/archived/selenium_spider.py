"""
Selenium 爬虫 —— 绕过WAF方案
=============================
不走API，直接用浏览器访问搜索页面，
从渲染后的HTML提取数据。

策略：
  1. Selenium打开www.51job.com（过WAF）
  2. 构造搜索URL在浏览器里打开
  3. 等待JS渲染完成后提取页面数据
  4. 翻页继续
  5. 详情页补充技能标签

优点：浏览器自然执行JS，WAF无感知
缺点：比API慢（但比被封好）
"""
import time
import random
import json
import csv
import os
import re
from datetime import datetime
from typing import List, Dict, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from loguru import logger

import config
from parser.job_parser import parse_list_item_from_html, parse_detail_item
from parser.salary_parser import parse_salary, normalize_city


class SeleniumSpider:
    """
    Selenium爬虫
    ------------
    用真实浏览器访问51job，从渲染页面提取数据。

    用法：
        spider = SeleniumSpider()
        spider.run()
    """

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.driver = None
        self.wait = None
        self.results = []
        self.csv_path = os.path.join(config.RAW_DIR, "raw_data.csv")
        self.checkpoint_file = os.path.join(config.LOG_DIR, "selenium_checkpoint.json")
        self.fieldnames = [
            "job_title", "salary_text", "salary_min", "salary_max", "salary_avg",
            "city", "district", "education", "experience",
            "company_name", "company_size", "industry",
            "skill_tags", "publish_date", "job_url",
            "keyword", "crawl_time",
        ]

    # ================================================================
    # 浏览器启动
    # ================================================================

    def _launch_browser(self):
        """启动Chrome + 反检测"""
        logger.info("[SELENIUM] Launching Chrome...")
        opts = Options()
        if self.headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1366,800")
        opts.add_argument("--lang=zh-CN")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)

        self.driver = webdriver.Chrome(options=opts)
        self.wait = WebDriverWait(self.driver, 15)

        # 注入反检测JS
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """})

        # 访问首页拿Cookie
        logger.info("   Accessing www.51job.com...")
        self.driver.get("https://www.51job.com/")
        time.sleep(5)
        logger.info(f"   Page loaded: {len(self.driver.page_source)} chars")

    # ================================================================
    # 搜索页面数据提取
    # ================================================================

    def search_keyword(self, keyword: str, max_pages: int = None) -> List[Dict]:
        """
        在浏览器里搜索一个关键词并翻页提取数据

        搜索URL方案：直接用51job的PC搜索页
        https://we.51job.com/pc/search?keyword=xxx
        这个页面是React SPA的一部分，在浏览器里能正常渲染
        """
        if max_pages is None:
            max_pages = config.MAX_PAGES

        results = []
        logger.info(f"[SEARCH] Keyword: {keyword}, max pages: {max_pages}")

        # 加载断点
        start_page = 1
        cp = self._load_checkpoint()
        if cp and cp.get("current_keyword") == keyword:
            start_page = cp.get("current_page", 1) + 1
            logger.info(f"   Resuming from page {start_page}")

        for page in range(start_page, max_pages + 1):
            logger.info(f"   Page {page}/{max_pages}...")

            # 构造搜索URL
            search_url = (
                f"https://we.51job.com/pc/search?"
                f"keyword={keyword}&searchType=2&sortType=0&metro="
                f"&pageNum={page}&pageSize={config.PAGE_SIZE}"
            )

            try:
                self.driver.get(search_url)
                # 等待职位列表渲染
                time.sleep(random.uniform(4, 7))

                # 检查是否被拦截
                page_text = self.driver.page_source
                if "滑块" in page_text or "验证" in page_text[:500]:
                    logger.warning(f"   Captcha detected, pausing 60s...")
                    time.sleep(60)
                    self.driver.get(search_url)
                    time.sleep(5)
                    page_text = self.driver.page_source
                    if "滑块" in page_text:
                        logger.error("   Still blocked, skipping")
                        self._save_checkpoint(keyword, page)
                        continue

                # 提取职位卡片
                # 51job SPA 页面结构：职位列表在 .joblist 或 .job-items 容器里
                items = self._extract_job_cards()
                if not items:
                    logger.info("   No more results, end of pagination")
                    break

                for item in items:
                    try:
                        parsed = self._parse_card(item, keyword)
                        if parsed and parsed.get("job_title"):
                            results.append(parsed)
                    except Exception as e:
                        logger.debug(f"   Card parse error: {e}")
                        continue

                logger.info(f"   Got {len(items)} cards, total: {len(results)}")

                # 保存断点
                self._save_checkpoint(keyword, page)

                # 达到目标数就停
                if len(results) >= config.JOBS_PER_KEYWORD:
                    logger.info(f"   Reached target {config.JOBS_PER_KEYWORD}")
                    break

                # 随机延时（模拟人类浏览）
                time.sleep(random.uniform(config.DELAY_MIN, config.DELAY_MAX))

            except Exception as e:
                logger.error(f"   Page error: {e}")
                self._save_checkpoint(keyword, page)
                time.sleep(10)
                continue

        return results

    def _extract_job_cards(self) -> list:
        """
        从当前页面提取职位卡片DOM元素

        51job SPA页面可能的职位列表结构：
        - .joblist-item (新版)
        - .job-item (通用)
        - [class*="joblist"] 下的卡片
        """
        cards = []

        # 尝试多种选择器
        selectors = [
            ".joblist-item",
            ".joblist .job-item",
            "[class*='joblist'] [class*='item']",
            ".j_joblist .e",
            ".el",
        ]

        for sel in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if elements and len(elements) > 5:
                    cards = elements
                    break
            except Exception:
                continue

        # 如果CSS选择器没找到，尝试从JSON数据提取
        # 51job SPA通常把初始数据存在某个script标签或window变量里
        if not cards:
            try:
                # 尝试从页面中提取 __NEXT_DATA__ 或 initialState
                script_data = self.driver.execute_script("""
                    // 尝试各种数据来源
                    if (window.__NEXT_DATA__) return JSON.stringify(window.__NEXT_DATA__);
                    if (window.__INITIAL_STATE__) return JSON.stringify(window.__INITIAL_STATE__);
                    // 查找包含"engine_search_result"的script标签
                    var scripts = document.querySelectorAll('script');
                    for (var s of scripts) {
                        if (s.textContent && s.textContent.indexOf('engine_search_result') > -1) {
                            return s.textContent;
                        }
                    }
                    return null;
                """)
                if script_data:
                    # 尝试从中提取职位数据
                    try:
                        data = json.loads(script_data)
                        # 递归搜索 job list
                        result = self._find_jobs_in_json(data)
                        if result:
                            logger.info(f"   Extracted {len(result)} jobs from page JSON")
                            # 返回伪DOM列表供parse_card处理
                            cards = result  # 不是DOM元素，是dict列表
                    except json.JSONDecodeError:
                        pass
            except Exception:
                pass

        return cards

    def _find_jobs_in_json(self, data, depth=0):
        """递归搜索JSON中的职位列表"""
        if depth > 5:
            return None
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            if any(k in data[0] for k in ["jobName", "job_name", "jobTitle"]):
                return data
        if isinstance(data, dict):
            for key in ["engine_search_result", "resultbody", "result", "jobList", "list", "items", "data"]:
                result = self._find_jobs_in_json(data.get(key), depth + 1)
                if result:
                    return result
        return None

    def _parse_card(self, card, keyword):
        """
        解析单个职位卡片

        参数card可能是：
        - Selenium WebElement（从DOM提取）
        - dict（从JSON提取）
        """
        if isinstance(card, dict):
            # JSON格式
            return {
                "job_title": card.get("jobName") or card.get("job_name") or "",
                "salary_text": card.get("providesalary") or card.get("salary") or "",
                "salary_min": None, "salary_max": None, "salary_avg": None,
                "city": card.get("workarea") or card.get("city") or "",
                "district": "",
                "education": card.get("degreefrom") or card.get("education") or "",
                "experience": card.get("workyear") or card.get("experience") or "",
                "company_name": card.get("companyName") or card.get("company_name") or "",
                "company_size": card.get("companySize") or card.get("companysize") or "",
                "industry": card.get("companyind_text") or card.get("industry") or "",
                "skill_tags": ", ".join(card.get("attribute", [])) if isinstance(card.get("attribute"), list) else "",
                "publish_date": card.get("issuedate") or "",
                "job_url": f"https://jobs.51job.com/all/{card.get('jobId','')}.html",
                "keyword": keyword,
                "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        # Selenium WebElement 格式
        try:
            html = card.get_attribute("innerHTML")
        except Exception:
            return None

        # 从HTML片段提取各字段
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        title_el = soup.select_one("[class*='job'] [class*='name'], [class*='title'], .jname")
        salary_el = soup.select_one("[class*='sal'], .sal")
        company_el = soup.select_one("[class*='com'], .cname")
        city_el = soup.select_one("[class*='area'], .area")

        result = {
            "job_title": title_el.get_text(strip=True) if title_el else "",
            "salary_text": salary_el.get_text(strip=True) if salary_el else "",
            "salary_min": None, "salary_max": None, "salary_avg": None,
            "city": city_el.get_text(strip=True) if city_el else "",
            "district": "",
            "education": "",
            "experience": "",
            "company_name": company_el.get_text(strip=True) if company_el else "",
            "company_size": "",
            "industry": "",
            "skill_tags": "",
            "publish_date": "",
            "job_url": "",
            "keyword": keyword,
            "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 补算薪资
        if result["salary_text"]:
            smin, smax, savg = parse_salary(result["salary_text"])
            result["salary_min"] = smin
            result["salary_max"] = smax
            result["salary_avg"] = savg

        return result

    # ================================================================
    # 断点续传
    # ================================================================

    def _save_checkpoint(self, keyword, page):
        cp = {"current_keyword": keyword, "current_page": page}
        try:
            with open(self.checkpoint_file, "w") as f:
                json.dump(cp, f)
        except Exception:
            pass

    def _load_checkpoint(self):
        if not os.path.exists(self.checkpoint_file):
            return None
        try:
            with open(self.checkpoint_file) as f:
                return json.load(f)
        except Exception:
            return None

    # ================================================================
    # CSV 存储
    # ================================================================

    def save_csv(self):
        if not self.results:
            return
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        with open(self.csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self.results)
        logger.info(f"[SAVE] {len(self.results)} records to {self.csv_path}")

    # ================================================================
    # 主入口
    # ================================================================

    def run(self, keywords: List[str] = None):
        if keywords is None:
            keywords = config.KEYWORDS

        logger.info("=" * 50)
        logger.info(f"SELENIUM SPIDER for 51job")
        logger.info(f"Keywords: {keywords}")
        logger.info("=" * 50)

        try:
            self._launch_browser()

            for kw in keywords:
                results = self.search_keyword(kw)
                self.results.extend(results)
                self.save_csv()
                logger.info(f"Progress: {len(self.results)} total")

            self._print_summary()

        finally:
            if self.driver:
                self.driver.quit()
                logger.info("Browser closed")

        return self.results

    def _print_summary(self):
        if not self.results:
            logger.warning("No data collected!")
            return
        kw_counts = {}
        for r in self.results:
            kw = r.get("keyword", "?")
            kw_counts[kw] = kw_counts.get(kw, 0) + 1
        logger.info(f"\nTotal: {len(self.results)} records")
        for kw, cnt in sorted(kw_counts.items()):
            logger.info(f"  {kw}: {cnt}")


if __name__ == "__main__":
    spider = SeleniumSpider(headless=False)
    spider.run()
