"""
51job 真实数据采集 - fetch() + 极慢节奏
========================================
fetch() → 干净JSON → 每页50条 → 15-20s间隔 → 每3页刷新浏览器

策略：模拟"极慢的人类浏览"，不触发WAF限速

运行：py -3.10 crawler/live_spider.py
"""
import time, random, json, csv, os, sys
from datetime import datetime
from urllib.parse import quote
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium_stealth import stealth
from loguru import logger

import config
from parser.salary_parser import parse_experience

FIELDNAMES = [
    "job_title","salary_text","salary_min","salary_max","salary_avg",
    "city","district","city_tier","education","experience","exp_min","exp_max",
    "company_name","company_size","industry",
    "skill_tags","publish_date","job_url","keyword","crawl_time",
]

TARGET_CITIES = ["广州", "深圳", "珠海", "肇庆"]


class LiveSpider:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.driver = None
        self.results = []
        self.seen_ids = set()
        self.csv_path = os.path.join(config.RAW_DIR, "raw_data.csv")
        self.cp_path = os.path.join(config.LOG_DIR, "live_checkpoint.json")

    def run(self):
        keywords = config.KEYWORDS
        print(f"\n{'='*55}")
        print(f"  51job LIVE - fetch() + slow rhythm")
        print(f"  Keywords: {keywords}  Cities: {TARGET_CITIES}")
        print(f"  ~20s/page, ~15min total")
        print(f"{'='*55}")

        try:
            self._launch()
            self._init_session()

            done_kw = self._load_done()

            for kw in keywords:
                if kw in done_kw:
                    print(f"[SKIP] {kw}")
                    continue
                self._search(kw)
                self._save()
                self._mark_done(kw)

            self._summary()
        except KeyboardInterrupt:
            print("\n[SAVE]")
            self._save()
        finally:
            if self.driver:
                self.driver.quit()

    def _launch(self):
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
        stealth(self.driver, languages=["zh-CN","zh"], vendor="Google Inc.",
                platform="Win32", webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine", fix_hairline=True)
        print("[OK] Chrome ready. DO NOT CLOSE THIS WINDOW.")

    def _init_session(self):
        """初始化浏览器session：直接访问搜索页建立WAF Cookie"""
        first_kw = config.KEYWORDS[0] if config.KEYWORDS else "数据分析"
        url = f"https://we.51job.com/pc/search?keyword={quote(first_kw)}&pageNum=1"
        self.driver.get(url)
        time.sleep(8)
        self.driver.execute_script("window.scrollTo(0, 400)")
        time.sleep(1)
        print("[OK] Session initialized")

    def _refresh_session(self, keyword: str):
        """刷新WAF cookie: 导航到搜索页让React自然渲染"""
        url = f"https://we.51job.com/pc/search?keyword={quote(keyword)}&pageNum=1"
        self.driver.get(url)
        time.sleep(8)
        print("  [refresh] Session renewed")

    def _fetch(self, keyword: str, page: int) -> list:
        """浏览器内fetch()调API，返回解析后的职位列表"""
        params = (f"api_key=51job&keyword={quote(keyword)}&searchType=2"
                  f"&jobArea=000000&pageNum={page}&pageSize=50"
                  f"&source=1&sortType=0")

        js = f"""
        async function _f() {{
            const r = await fetch('https://we.51job.com/api/job/search-pc?{params}',
                {{ credentials:'include',
                   headers:{{'Accept':'application/json',
                            'Referer':'https://we.51job.com/pc/search'}} }});
            return await r.text();
        }}
        return await _f();
        """
        try:
            raw = self.driver.execute_script(js)
            if not raw or len(str(raw)) < 500:
                return None
            if "aliyun_waf" in str(raw)[:800].lower():
                return "WAF"
            if "滑块" in str(raw)[:500] or "验证" in str(raw)[:500]:
                return "WAF"

            data = json.loads(raw)
            items = (data.get("engine_search_result") or data.get("resultbody"))
            if isinstance(items, dict):
                items = (items.get("job",{}).get("items") or
                        items.get("items") or items.get("list") or [])
            if not isinstance(items, list):
                items = []

            result = []
            for item in items:
                if not isinstance(item, dict):
                    continue

                # 新版 API 字段解析
                job_area = item.get("jobAreaString") or item.get("workAreaString") or ""
                city, district = self._split_city(job_area)
                exp_text = item.get("workYearString", "")
                exp_min, exp_max = parse_experience(exp_text)

                result.append({
                    "job_title": item.get("jobName", ""),
                    "salary_text": item.get("provideSalaryString", ""),
                    "salary_min": None, "salary_max": None, "salary_avg": None,
                    "city": city,
                    "district": district,
                    "city_tier": config.CITY_TIER.get(city, "其他"),
                    "education": item.get("degreeString", ""),
                    "experience": exp_text,
                    "exp_min": exp_min,
                    "exp_max": exp_max,
                    "company_name": item.get("companyName", ""),
                    "company_size": "",
                    "industry": item.get("industryType1Str", ""),
                    "skill_tags": ", ".join(item.get("jobTags", [])) if isinstance(item.get("jobTags"), list) else "",
                    "publish_date": item.get("issueDateString", ""),
                    "job_url": f"https://jobs.51job.com/all/{item.get('jobId','')}.html",
                    "keyword": keyword,
                    "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
            return result
        except Exception:
            return None

    def _split_city(self, area_str: str) -> tuple:
        """把 '广州·天河区' 拆成 (city, district)"""
        if not area_str:
            return "", ""
        parts = area_str.replace("·", "-").split("-")
        city = parts[0].strip()
        district = parts[1].strip() if len(parts) > 1 else ""
        return city, district

    def _search(self, keyword: str):
        target = min(config.JOBS_PER_KEYWORD, 100)
        results = []
        fails = 0
        pages_since_refresh = 0

        print(f"\n[{keyword}] target={target}")

        for page in range(1, 100):
            if len(results) >= target:
                break
            if fails >= 8:
                print(f"  [STOP] Too many failures")
                break

            # 🔥 极慢节奏
            delay = random.uniform(15, 22)
            print(f"  Page {page}... (waiting {delay:.0f}s)", end="", flush=True)
            time.sleep(delay)

            items = self._fetch(keyword, page)

            if items == "WAF" or items is None:
                fails += 1
                print(f" FAIL({fails})")
                # 刷新session
                if fails % 2 == 0:
                    self._refresh_session(keyword)
                continue

            if not items:
                fails += 1
                print(f" EMPTY({fails})")
                continue

            fails = 0
            pages_since_refresh += 1

            # 城市过滤
            city_items = [it for it in items
                         if any(c in (it.get("city") or "") for c in TARGET_CITIES)]

            # 去重
            new_items = []
            for it in city_items:
                jid = it.get("job_url","")
                if jid and jid not in self.seen_ids:
                    self.seen_ids.add(jid)
                    new_items.append(it)

            results.extend(new_items)
            print(f" {len(items)}/{len(city_items)}/{len(new_items)} (total {len(results)})")

            # 🔥 每3页刷新一次浏览器session
            if pages_since_refresh >= 3:
                self._refresh_session(keyword)
                pages_since_refresh = 0

        city_dist = Counter(r.get("city","?") for r in results)
        print(f"[DONE] {keyword}: {len(results)} jobs {dict(city_dist)}")
        self.results.extend(results)

    def _save(self):
        if not self.results:
            return
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        with open(self.csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self.results)

    def _load_done(self):
        if not os.path.exists(self.cp_path):
            return set()
        with open(self.cp_path) as f:
            return set(json.load(f).get("done", []))

    def _mark_done(self, kw):
        done = list(self._load_done()) + [kw]
        with open(self.cp_path, "w") as f:
            json.dump({"done": done}, f)

    def _summary(self):
        if not self.results:
            print("\n[EMPTY] No data")
            return
        kw = Counter(r.get("keyword","?") for r in self.results)
        city = Counter(r.get("city","?") for r in self.results)
        print(f"\n{'='*50}")
        print(f"TOTAL: {len(self.results)} real 51job jobs")
        print(f"Keywords: {dict(kw)}")
        print(f"Cities: {dict(city)}")
        print(f"CSV: {self.csv_path}")


if __name__ == "__main__":
    LiveSpider().run()
