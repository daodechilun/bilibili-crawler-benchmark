"""
人机协作采集 ⚡
==============
1. 浏览器弹出 → 你手动过滑块 → 看到职位列表
2. 脚本自动检测到数据出现 → 接管采集
3. 4个关键词各500条，翻页全自动

运行：py -3.10 crawler/manual_then_auto.py
"""
import time, random, json, csv, os, sys
from datetime import datetime
from typing import List, Dict, Optional

# 确保能找到 config 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium_stealth import stealth
from loguru import logger

import config

FIELDNAMES = [
    "job_title","salary_text","salary_min","salary_max","salary_avg",
    "city","district","education","experience",
    "company_name","company_size","industry",
    "skill_tags","publish_date","job_url","keyword","crawl_time",
]


class ManualThenAuto:
    def __init__(self):
        self.driver = None
        self.results = []
        self.csv_path = os.path.join(config.RAW_DIR, "raw_data.csv")

    def run(self, keywords=None):
        if keywords is None:
            keywords = config.KEYWORDS

        print("\n" + "=" * 60)
        print("  MANUAL + AUTO SPIDER")
        print("=" * 60)

        try:
            self._launch()
            self._warmup()

            # ================================================================
            # 阶段1：等你手动过验证
            # ================================================================
            print("\n" + "=" * 60)
            print("  >>> NOW: Browser will open 51job search page")
            print("  >>> If you see a SLIDER CAPTCHA, drag it to the right")
            print("  >>> Wait until you see JOB LISTINGS on the page")
            print("  >>> Script will auto-detect and start collecting...")
            print("=" * 60 + "\n")

            self.driver.get("https://we.51job.com/pc/search?keyword=Python&pageNum=1")
            print("[WAIT] Checking for job data every 3 seconds...")

            # 🔥 轮询检测：等页面出现职位数据
            ready = False
            for i in range(120):  # 最多等6分钟
                time.sleep(3)
                has_data = self._check_page_has_jobs()
                if has_data:
                    print(f"\n[READY] Job data detected! ({i*3}s elapsed)")
                    ready = True
                    break
                if i % 5 == 0:
                    body_snippet = self._get_body_snippet()
                    print(f"  [{i*3}s] Waiting... Page shows: {body_snippet[:80]}")

            if not ready:
                # 可能页面加载了但数据格式不同，尝试直接fetch
                print("\n[WARN] No job data detected in DOM. Trying fetch() directly...")
                raw = self._fetch_api("Python", 1)
                if raw:
                    items = self._parse_response(raw, "Python")
                    if items:
                        print(f"[OK] fetch() works! Got {len(items)} jobs")
                        ready = True

            if not ready:
                print("\n[FAIL] Could not get job data.")
                print("Please manually check the browser and try again.")
                return

            # ================================================================
            # 阶段2：自动采集
            # ================================================================
            print("\n" + "=" * 60)
            print("  AUTO COLLECTION STARTING")
            print(f"  Keywords: {keywords}")
            print(f"  Target: {config.JOBS_PER_KEYWORD} each")
            print("=" * 60 + "\n")

            for kw in keywords:
                print(f"\n>>> [{kw}] Starting...")
                kw_results = self._auto_search(kw)
                self.results.extend(kw_results)
                self._save_csv()
                print(f">>> [{kw}] Done: {len(kw_results)} jobs")

            self._summary()

        except KeyboardInterrupt:
            print("\nInterrupted. Saving...")
            self._save_csv()
        finally:
            if self.driver:
                self.driver.quit()
                print("Browser closed")

        return self.results

    def _launch(self):
        opts = Options()
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1366,800")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)

        self.driver = webdriver.Chrome(options=opts)
        stealth(self.driver, languages=["zh-CN","zh"], vendor="Google Inc.",
                platform="Win32", webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine", fix_hairline=True)
        print("[LAUNCH] Stealth Chrome ready")

    def _warmup(self):
        self.driver.get("https://www.51job.com/")
        time.sleep(4)
        # 模拟真人：滚动两下
        self.driver.execute_script("window.scrollTo(0, 400)")
        time.sleep(1)
        self.driver.execute_script("window.scrollTo(0, 200)")
        print(f"[WARMUP] Homepage loaded ({len(self.driver.page_source)} chars)")

    def _get_body_snippet(self):
        try:
            body = self.driver.find_element("tag name", "body")
            text = body.text
            return text[:200] if text else "(empty)"
        except Exception:
            return "(error)"

    def _check_page_has_jobs(self):
        """
        检查页面是否包含职位数据

        方法1: 检查DOM里有没有职位卡片元素
        方法2: 检查页面文字里有没有典型的职位/薪资关键词
        """
        try:
            ps = self.driver.page_source

            # 检查WAF/滑块还在不在
            if "滑块" in ps[:2000] or "aliyun_waf" in ps[:2000].lower():
                return False

            # 检查职位相关的DOM元素
            from selenium.webdriver.common.by import By
            for sel in [".joblist-item", "[class*='joblist'] [class*='item']",
                        ".j_joblist .e", ".job-item"]:
                try:
                    els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    if len(els) >= 3:
                        return True
                except Exception:
                    continue

            # 检查页面文本里有没有典型的薪资模式（如 15-25K, 8千-1.2万）
            import re
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            salary_patterns = re.findall(r'\d+[kK千]-?\d*[kK万千]?', body_text)
            if len(salary_patterns) >= 2:
                return True

            # 检查文本长度（空页面或WAF页很短）
            if len(body_text) > 2000 and "Python" in body_text:
                if "搜索发现" in body_text and "Python" in body_text:
                    # 搜索建议出现了但没有职位——可能数据还没加载
                    return False
                return True

        except Exception:
            pass
        return False

    def _fetch_api(self, keyword: str, page: int) -> Optional[str]:
        """浏览器内fetch()调API"""
        qs = f"api_key=51job&keyword={keyword}&searchType=2&jobArea=000000&pageNum={page}&pageSize=50&source=1&sortType=0"
        js = f"""
        async function f() {{
            try {{
                const r = await fetch('https://we.51job.com/api/job/search-pc?' + '{qs}', {{
                    credentials: 'include',
                    headers: {{ 'Accept': 'application/json', 'Referer': 'https://we.51job.com/' }}
                }});
                return await r.text();
            }} catch(e) {{ return 'ERR:' + e.message; }}
        }}
        return await f();
        """
        try:
            raw = self.driver.execute_script(js)
            if raw and "滑块" not in str(raw) and "aliyun_waf" not in str(raw)[:500] and len(str(raw)) > 200:
                return raw
        except Exception:
            pass
        return None

    def _parse_response(self, raw: str, keyword: str) -> List[Dict]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []

        items = None
        result = data.get("engine_search_result") or data.get("resultbody")
        if isinstance(result, list):
            items = result
        elif isinstance(result, dict):
            job = result.get("job", {})
            items = job.get("items", []) if isinstance(job, dict) else []
            if not items:
                items = result.get("items") or result.get("list")

        parsed = []
        for item in (items or []):
            if not isinstance(item, dict):
                continue
            skill_raw = item.get("attribute", [])
            skill_tags = ", ".join(skill_raw) if isinstance(skill_raw, list) else str(skill_raw)
            parsed.append({
                "job_title": item.get("jobName",""),
                "salary_text": item.get("providesalary",""),
                "salary_min": None, "salary_max": None, "salary_avg": None,
                "city": item.get("workarea",""),
                "district": "",
                "education": item.get("degreefrom",""),
                "experience": item.get("workyear",""),
                "company_name": item.get("companyName",""),
                "company_size": item.get("companySize",""),
                "industry": item.get("companyind_text",""),
                "skill_tags": skill_tags,
                "publish_date": item.get("issuedate",""),
                "job_url": f"https://jobs.51job.com/all/{item.get('jobId','')}.html",
                "keyword": keyword,
                "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
        return parsed

    def _auto_search(self, keyword: str) -> List[Dict]:
        results = []
        fails = 0
        target = min(config.JOBS_PER_KEYWORD, 800)

        for page in range(1, target // 50 + 5):  # 每页50条，加5页余量
            if len(results) >= target:
                break

            time.sleep(random.uniform(config.DELAY_MIN, config.DELAY_MAX))

            raw = self._fetch_api(keyword, page)
            if not raw:
                fails += 1
                logger.warning(f"   Page {page} fail ({fails}/3)")
                if fails >= 3:
                    logger.error("   Too many failures, stopping keyword")
                    break
                time.sleep(20)
                continue

            fails = 0
            items = self._parse_response(raw, keyword)
            if not items:
                logger.info(f"   Page {page}: no more results")
                break

            results.extend(items)
            print(f"   [{keyword}] Page {page}: {len(items)} jobs (total {len(results)})")

        return results

    def _save_csv(self):
        if not self.results:
            return
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        with open(self.csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self.results)

    def _summary(self):
        if not self.results:
            print("\n[RESULT] No data collected")
            return
        kw = {}
        for r in self.results:
            k = r.get("keyword","?")
            kw[k] = kw.get(k, 0) + 1
        print(f"\n{'='*40}")
        print(f"TOTAL: {len(self.results)} jobs")
        for k, c in sorted(kw.items()):
            print(f"  {k}: {c}")
        print(f"CSV: {self.csv_path}")


if __name__ == "__main__":
    spider = ManualThenAuto()
    spider.run()
