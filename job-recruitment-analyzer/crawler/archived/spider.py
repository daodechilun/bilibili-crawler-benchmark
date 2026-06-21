"""
51job 招聘数据采集主爬虫
=======================

流程：
  关键词列表 → 搜索API翻页 → 提取列表数据 → 详情页补充信息 → 保存CSV

技术栈：
  - requests.Session：维持Cookie，发HTTP请求
  - 51job新版API：返回JSON，解析准确率远高于HTML
  - 代理池 + UA池 + 随机延时：反反爬三件套

使用方式：
  python -m crawler.spider        # 单独运行爬虫
  python main.py                  # 从主入口运行
"""
import time
import random
import json
import csv
import os
from datetime import datetime
from typing import Optional, Dict, List
from urllib.parse import urlencode, quote

import requests
from loguru import logger

import config
from crawler.ua_pool import get_random_ua
from crawler.proxy_pool import proxy_pool
from crawler.cookie_mgr import cookie_mgr
from parser.job_parser import parse_list_item, parse_detail_item, normalize_salary_field


class JobSpider:
    """
    51job 岗位爬虫
    -------------
    负责完整的采集流程：搜索 → 列表提取 → 详情获取 → CSV存储

    核心方法：
        run()           启动采集（主入口）
        search()        搜索一个关键词的所有页面
        fetch_detail()  获取单个岗位的详情信息
        save_to_csv()   保存数据到CSV
    """

    def __init__(self):
        """初始化爬虫：准备代理池、UA池、Cookie管理器、断点续传状态"""
        self.session = cookie_mgr.get_session()
        self.results: List[Dict] = []          # 采集结果暂存
        self.checkpoint_file = os.path.join(config.LOG_DIR, "checkpoint.json")
        self.csv_path = os.path.join(config.RAW_DIR, "raw_data.csv")
        self.fieldnames = [
            "job_title", "salary_text", "salary_min", "salary_max", "salary_avg",
            "city", "district", "education", "experience",
            "company_name", "company_size", "industry",
            "skill_tags", "publish_date", "job_url",
            "keyword", "crawl_time",
        ]
        self._consecutive_blocks = 0  # 🔥 连续被拦截计数器（触发全局休眠用）

    # ================================================================
    # 核心：带反爬的 HTTP 请求
    # ================================================================

    def _safe_request(
        self,
        url: str,
        method: str = "GET",
        params: dict = None,
        headers_extra: dict = None,
        use_proxy: bool = True,
        retries: int = None,
    ) -> Optional[requests.Response]:
        """
        发送一个"安全"的 HTTP 请求

        "安全"的含义：
        1. 每次随机换 User-Agent
        2. 自动带上 Cookie
        3. 随机延时（模拟人类浏览节奏）
        4. 代理轮换（如果启用）
        5. 失败自动重试（最多3次，指数退避）
        6. 检测是否被反爬（验证码、封IP等）

        返回 Response 对象，失败返回 None
        """
        if retries is None:
            retries = config.MAX_RETRIES

        # 准备请求头
        headers = {
            "User-Agent": get_random_ua(),  # 每次换一个UA
            "Referer": "https://we.51job.com/",
            "Origin": "https://we.51job.com",
        }
        if headers_extra:
            headers.update(headers_extra)

        # 🔥 检查代理降级：如果可用代理<3个，自动走直连+长延时
        if use_proxy and proxy_pool.should_use_direct():
            use_proxy = False
            logger.debug("🔄 代理池不足，本次请求走直连模式")

        # 准备代理
        proxy = proxy_pool.get() if use_proxy else None
        proxies = proxy if proxy else None

        # 直连模式用更长延时（1.5倍），降低被封风险
        delay_multiplier = 1.5 if not use_proxy else 1.0

        # 核心重试循环
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                # 请求前随机延时
                if attempt == 1:
                    time.sleep(random.uniform(config.DELAY_MIN, config.DELAY_MAX) * delay_multiplier)
                else:
                    wait = config.RETRY_BASE_WAIT * (2 ** (attempt - 1))
                    logger.debug(f"🔄 第 {attempt} 次重试，等待 {wait:.0f} 秒...")
                    time.sleep(wait)

                # 发请求
                if method.upper() == "GET":
                    resp = self.session.get(
                        url, params=params, headers=headers,
                        proxies=proxies, timeout=15
                    )
                else:
                    resp = self.session.post(
                        url, data=params, headers=headers,
                        proxies=proxies, timeout=15
                    )

                # 检查是否被反爬
                block_check = self._detect_block(resp)
                if block_check:
                    logger.warning(f"⚠️ 检测到反爬拦截: {block_check}")
                    self._consecutive_blocks += 1  # 🔥 累加拦截计数
                    if proxy:
                        proxy_pool.report(proxy, ok=False)
                    # 被拦了换个代理重试
                    proxy = proxy_pool.get()
                    proxies = proxy if proxy else None
                    continue

                # 请求成功 → 重置拦截计数
                self._consecutive_blocks = 0

                if resp.status_code == 200:
                    if proxy:
                        proxy_pool.report(proxy, ok=True)
                    return resp
                else:
                    logger.debug(f"HTTP {resp.status_code}，重试...")

            except requests.exceptions.Timeout as e:
                last_error = e
                logger.debug(f"请求超时: {url[:80]}...")
            except requests.exceptions.ConnectionError as e:
                last_error = e
                logger.debug(f"连接失败: {url[:80]}...")
                if proxy:
                    proxy_pool.report(proxy, ok=False)
                    proxy = proxy_pool.get()
                    proxies = proxy if proxy else None
            except Exception as e:
                last_error = e
                logger.debug(f"请求异常: {type(e).__name__}: {e}")

        # 所有重试都失败了
        logger.error(f"❌ 请求失败（{retries}次重试后）: {url[:80]}...，最后错误: {last_error}")
        return None

    def _detect_block(self, resp: requests.Response) -> Optional[str]:
        """
        检测是否被网站反爬拦截

        判断方法：
        1. 页面内容不正常（太短、空JSON、错误码）
        2. 出现了验证码关键词
        3. 被重定向到登陆页或验证页

        返回：拦截原因字符串，没被拦返回 None
        """
        if resp is None:
            return "Response为None"

        # 检查状态码
        if resp.status_code in (403, 429, 503, 504):
            return f"HTTP {resp.status_code} 被拒绝"

        # 检查是否被重定向到验证页面
        if "verify" in resp.url.lower() or "captcha" in resp.url.lower():
            return "被重定向到验证页面"

        # 检查内容长度（太短说明不是正常数据）
        content_len = len(resp.text)
        if content_len < 100:
            return f"响应内容过短（{content_len}字节）"

        # 检查是否包含验证码关键词
        text_lower = resp.text[:500].lower()
        block_keywords = ["验证", "captcha", "滑块", "请稍后再试", "访问频率", "ip限制"]
        for kw in block_keywords:
            if kw in text_lower:
                return f"响应包含反爬关键词: {kw}"

        # 尝试解析JSON，检查业务错误码
        try:
            data = resp.json()
            if isinstance(data, dict):
                code = data.get("code") or data.get("status") or data.get("errno")
                # 51job API 通常 code=0 或 code=200 表示成功
                if code is not None and code not in (0, 200, "0", "200"):
                    return f"API返回错误码: {code}, 消息: {data.get('message', '')}"
        except (json.JSONDecodeError, ValueError):
            pass

        return None  # 没被拦截，一切正常

    # ================================================================
    # 搜索与翻页
    # ================================================================

    def search(self, keyword: str, max_pages: int = None, start_page: int = 1) -> List[Dict]:
        """
        搜索一个关键词下的所有岗位（自动翻页）

        51job 搜索API说明：
        - 端点: https://we.51job.com/api/job/search-pc
        - 方法: GET
        - 关键参数:
            keyword    → 搜索关键词
            pageNum    → 页码（从1开始）
            pageSize   → 每页条数（最大50）
            jobArea    → 区域代码（000000=全国）
            api_key    → 固定值 51job
            searchType → 2（全文搜索）
            sortType   → 0（默认排序）

        参数：
            keyword: 搜索关键词，如 "数据分析"
            max_pages: 最多翻几页，默认用 config.MAX_PAGES
            start_page: 🔥 从第几页开始（断点续传用）
        返回：这一关键词下的所有岗位列表
        """
        if max_pages is None:
            max_pages = config.MAX_PAGES

        keyword_results = []
        logger.info(f"🔍 开始搜索关键词: 【{keyword}】，计划翻 {max_pages} 页，从第 {start_page} 页开始")

        for page in range(start_page, max_pages + 1):
            logger.info(f"📄 [{keyword}] 第 {page}/{max_pages} 页...")

            # 构造搜索参数
            params = {
                "api_key": "51job",
                "timestamp": int(time.time() * 1000),
                "keyword": keyword,
                "searchType": "2",
                "function": "",
                "industry": "",
                "jobArea": "000000",
                "jobArea2": "",
                "landmark": "",
                "metro": "",
                "salary": "",
                "workYear": "",
                "degree": "",
                "companyType": "",
                "companySize": "",
                "jobType": "",
                "issueDate": "",
                "sortType": "0",
                "pageNum": page,
                "requestId": "",
                "pageSize": config.PAGE_SIZE,
                "source": "1",
                "accountid": "",
            }

            # 🔥 前3页+代理不足时走直连，后面看情况
            use_proxy_now = (page > 3) and not proxy_pool.should_use_direct()

            # 发送搜索请求
            resp = self._safe_request(
                config.API_SEARCH_URL,
                method="GET",
                params=params,
                headers_extra={
                    "Referer": f"https://we.51job.com/pc/search?keyword={quote(keyword)}",
                },
                use_proxy=use_proxy_now,
            )

            if resp is None:
                logger.warning(f"⏸️ [{keyword}] 第 {page} 页请求失败，保存断点后跳过")
                self._save_checkpoint(keyword, page)
                continue

            # 🔥 JSON解析外层加try-except，脏数据不崩进程
            try:
                data = resp.json()
            except (json.JSONDecodeError, ValueError, AttributeError) as e:
                logger.warning(f"⚠️ [{keyword}] 第 {page} 页返回不是有效JSON: {e}")
                self._save_checkpoint(keyword, page)
                continue

            # 🔥 51job API多路径兜底提取
            job_list = self._extract_job_list(data)
            if not job_list:
                logger.info(f"🏁 [{keyword}] 第 {page} 页没有数据，可能已翻到最后一页")
                self._save_checkpoint(keyword, page, finished=True)
                break

            # 🔥 逐条解析，坏数据跳过不崩
            for item in job_list:
                try:
                    parsed = parse_list_item(item, keyword)
                    if parsed and parsed.get("job_title"):
                        keyword_results.append(parsed)
                except Exception as e:
                    logger.debug(f"⚠️ 单条数据解析失败，跳过: {e}")
                    continue

            logger.info(f"  ✅ [{keyword}] 第 {page} 页获取 {len(job_list)} 条，累计 {len(keyword_results)} 条")

            # 每翻完一页保存断点
            self._save_checkpoint(keyword, page)

            # 翻到目标数量就停
            if len(keyword_results) >= config.JOBS_PER_KEYWORD:
                logger.info(f"🏁 [{keyword}] 已达到目标数量 {config.JOBS_PER_KEYWORD}，停止翻页")
                self._save_checkpoint(keyword, page, finished=True)
                break

        logger.info(f"✅ 关键词【{keyword}】采集完成，共 {len(keyword_results)} 条")
        return keyword_results

    def _extract_job_list(self, data: dict) -> list:
        """
        从51job API返回的JSON中提取岗位列表

        兼容多种API返回格式（51job可能改版，多写几个路径兜底）：
        - 标准路径: engine_search_result
        - 备用路径: resultbody.job.items
        - 嵌套路径: 各种可能的层级

        参数：
            data: API返回的完整JSON
        返回：
            岗位列表（list of dict）
        """
        if not isinstance(data, dict):
            return []

        # 路径1: 标准51job新版API格式
        result = data.get("engine_search_result") or data.get("resultbody")
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            # 路径2: resultbody → job → items
            job = result.get("job")
            if isinstance(job, dict):
                items = job.get("items") or job.get("item") or job.get("list")
                if isinstance(items, list):
                    return items
            # 路径3: resultbody → items
            items = result.get("items") or result.get("list") or result.get("data")
            if isinstance(items, list):
                return items

        # 路径4: data → list
        for key in ["list", "data", "items", "jobs", "result"]:
            val = data.get(key)
            if isinstance(val, list):
                return val

        return []

    # ================================================================
    # 详情页抓取（补充技能标签、详细描述等字段）
    # ================================================================

    def fetch_details(self, job_list: List[Dict], max_details: int = None) -> List[Dict]:
        """
        为列表中的每个岗位抓取详情页，补充技能标签等缺失字段

        为什么要抓详情页：
        - 列表页只有岗位名、薪资、城市等基本信息
        - 技能标签、详细JD在详情页里
        - 但不是每个岗位都需要详情页（列表页可能已经有了）

        🔥 详情页比列表页反爬更严，所以：
        - 延时更长（4~8秒，比列表页的3~8秒更温柔）
        - 连续3次被拦截 → 全局休眠60秒（模拟人类休息）
        - 被拦5次 → 直接放弃详情抓取，保住已有数据

        参数：
            job_list: 列表页采集的岗位数据
            max_details: 最多抓几个详情页（None=全部）
        返回：补充了详情字段的岗位列表
        """
        if max_details is None:
            max_details = len(job_list)
        max_details = min(max_details, len(job_list))

        logger.info(f"📋 开始抓取详情页，共 {max_details} 个...")
        detail_count = 0
        detail_blocks = 0  # 🔥 详情页被拦截计数

        for i, job in enumerate(job_list[:max_details]):
            # 如果列表页已经有技能标签了，跳过
            if job.get("skill_tags") and job["skill_tags"] != "无":
                continue

            job_id = job.get("job_id") or job.get("encrypt_job_id")
            if not job_id:
                continue

            # 🔥 详情页专属延时（比列表页更温柔）
            time.sleep(random.uniform(config.DETAIL_DELAY_MIN, config.DETAIL_DELAY_MAX))

            detail_url = f"{config.API_DETAIL_URL}?jobId={job_id}"
            resp = self._safe_request(detail_url, use_proxy=True)

            if resp is None:
                detail_blocks += 1
                # 🔥 连续3次被拦 → 全局休眠60秒，模拟人类喝杯咖啡
                if detail_blocks >= 3:
                    logger.warning(f"☕ 详情页连续被拦 {detail_blocks} 次，全局休眠 60 秒...")
                    time.sleep(60)
                    detail_blocks = 0  # 重置
                # 🔥 累计5次被拦 → 放弃详情抓取
                if self._consecutive_blocks >= 5:
                    logger.warning("⚠️ 累计被拦5次，放弃详情页采集，保住已有数据")
                    break
                continue

            try:
                detail_data = resp.json()
                detail_info = parse_detail_item(detail_data)
                job.update({k: v for k, v in detail_info.items() if v})
                detail_count += 1
                detail_blocks = 0  # 成功后重置
            except (json.JSONDecodeError, AttributeError, ValueError, KeyError) as e:
                logger.debug(f"⚠️ 详情解析失败: {e}")
                continue

            # 每50条打印一次进度
            if (i + 1) % 50 == 0:
                logger.info(f"  详情页进度: {i+1}/{max_details}")

        logger.info(f"✅ 详情页采集完成，补充了 {detail_count} 条详情")
        return job_list

    # ================================================================
    # 断点续传（🔥 JSON格式，记录关键词+页码+完成状态）
    # ================================================================

    def _save_checkpoint(self, keyword: str, page: int, finished: bool = False):
        """
        保存采集进度（断点续传）

        🔥 JSON格式记录：
        - 当前爬到哪个关键词的哪一页
        - 哪些关键词已经全部完成（finished_keywords）
        - 下次启动时自动跳过已完成的关键词 + 从中断页码继续

        如果爬虫中途崩了，重新运行 python main.py crawl 即可接上。
        """
        try:
            # 加载已有断点数据
            cp = {}
            if os.path.exists(self.checkpoint_file):
                try:
                    with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                        cp = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    cp = {}

            finished_kws = set(cp.get("finished_keywords", []))

            if finished:
                # 这个关键词全部爬完了，加入完成列表
                finished_kws.add(keyword)
                # 清除current，因为要换下一个关键词了
                cp["current_keyword"] = None
                cp["current_page"] = None
            else:
                cp["current_keyword"] = keyword
                cp["current_page"] = page

            cp["finished_keywords"] = list(finished_kws)
            cp["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(self.checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(cp, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_checkpoint(self) -> dict:
        """
        读取断点续传数据

        🔥 返回结构：
        {
            "current_keyword": "数据分析",    # 上次断在哪个关键词
            "current_page": 8,                # 上次断在第几页（从这个关键词的第9页继续）
            "finished_keywords": ["Python开发"],  # 已完成的关键词列表
            "updated_at": "2025-06-18 14:30:00"
        }
        文件不存在或损坏返回空字典。
        """
        if not os.path.exists(self.checkpoint_file):
            return {}
        try:
            with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            return {}

    # ================================================================
    # CSV 存储
    # ================================================================

    def save_to_csv(self, data: List[Dict], filepath: str = None, append: bool = False):
        """
        把采集结果保存为 CSV 文件

        参数：
            data: 岗位数据列表
            filepath: CSV文件路径，默认用 config 里的路径
            append: True=追加写入, False=覆盖写入
        """
        if filepath is None:
            filepath = self.csv_path

        mode = "a" if append else "w"
        write_header = not append or not os.path.exists(filepath)

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, mode, newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames, extrasaction="ignore")
            if write_header:
                writer.writeheader()
            writer.writerows(data)

        logger.info(f"💾 数据已保存到: {filepath}，共 {len(data)} 条")

    # ================================================================
    # 主入口：一键启动采集
    # ================================================================

    def run(self, keywords: List[str] = None, skip_details: bool = False):
        """
        启动完整采集流程

        步骤：
        1. 刷新代理池
        2. 🔥 读取JSON断点，精准恢复
        3. 逐个关键词搜索并翻页（跳过已完成的，未完成的从中断页继续）
        4. （可选）抓取详情页补充技能标签
        5. 保存最终CSV

        参数：
            keywords: 要搜索的关键词列表，默认用 config.KEYWORDS
            skip_details: True=跳过详情页（纯列表模式，速度快但缺字段）
        """
        if keywords is None:
            keywords = config.KEYWORDS

        # 启动时刷新代理池
        logger.info("🔄 初始化代理池...")
        proxy_pool.refresh()

        # 🔥 读取JSON断点
        cp = self._load_checkpoint()
        finished_keywords = set(cp.get("finished_keywords", []))
        current_kw = cp.get("current_keyword")
        current_page = cp.get("current_page") or 0

        if cp:
            logger.info(f"📌 检测到断点文件:")
            logger.info(f"   已完成的关键词: {finished_keywords}")
            logger.info(f"   上次中断: 【{current_kw}】第 {current_page} 页")
            if current_kw and current_page:
                logger.info(f"   🔥 将从【{current_kw}】第 {current_page + 1} 页继续")
        else:
            logger.info("📌 未检测到断点，从头开始采集")

        logger.info("=" * 60)
        logger.info(f"🚀 51job 招聘数据采集启动")
        logger.info(f"   关键词: {keywords}")
        logger.info(f"   每个关键词目标: {config.JOBS_PER_KEYWORD} 条")
        logger.info(f"   目标城市: {config.TARGET_CITIES}")
        logger.info(f"   当前代理池: {proxy_pool.count()} 个可用 | 降级模式: {'是' if proxy_pool.should_use_direct() else '否'}")
        logger.info("=" * 60)

        all_results = []

        for keyword in keywords:
            # 🔥 已完成的关键词直接跳过
            if keyword in finished_keywords:
                logger.info(f"⏭️ 关键词【{keyword}】已在断点中标记为完成，跳过")
                continue

            # 🔥 如果是上次中断的关键词，从中断页+1继续；否则从第1页开始
            start_page = 1
            if keyword == current_kw and current_page > 0:
                start_page = current_page + 1
                logger.info(f"🔥 【{keyword}】从断点恢复，从第 {start_page} 页继续")

            # 搜索+翻页
            kw_results = self.search(keyword, start_page=start_page)
            all_results.extend(kw_results)

            # 🔥 爬完这个关键词后标记为完成
            self._save_checkpoint(keyword, 0, finished=True)

            # 每完成一个关键词就存一份CSV（步步为营）
            self.save_to_csv(all_results, append=False)
            logger.info(f"📊 当前总进度: {len(all_results)} 条 / 目标 ~{len(keywords) * config.JOBS_PER_KEYWORD} 条")

        # 🔥 全部完成后删除断点文件（任务圆满完成）
        if os.path.exists(self.checkpoint_file):
            os.remove(self.checkpoint_file)
            logger.info("🗑️ 断点文件已清理（全部完成）")

        # 可选：抓详情页补充技能标签
        if not skip_details and all_results:
            logger.info("\n🔎 开始补充详情页信息...")
            all_results = self.fetch_details(all_results)

        # 最终保存
        self.save_to_csv(all_results, append=False)

        # 打印统计
        self._print_summary(all_results)

        return all_results

    def _print_summary(self, results: List[Dict]):
        """打印采集结果摘要"""
        if not results:
            logger.warning("⚠️ 没有采集到任何数据！")
            return

        # 统计各关键词数量
        keyword_counts = {}
        city_counts = {}
        for r in results:
            kw = r.get("keyword", "未知")
            keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
            city = r.get("city", "未知")
            city_counts[city] = city_counts.get(city, 0) + 1

        logger.info("\n" + "=" * 60)
        logger.info("📊 采集完成统计")
        logger.info(f"   总条数: {len(results)}")
        logger.info(f"   各关键词:")
        for kw, cnt in sorted(keyword_counts.items(), key=lambda x: -x[1]):
            logger.info(f"     {kw}: {cnt} 条")
        logger.info(f"   城市覆盖 TOP10:")
        for city, cnt in sorted(city_counts.items(), key=lambda x: -x[1])[:10]:
            logger.info(f"     {city}: {cnt} 条")
        logger.info(f"   CSV文件: {self.csv_path}")
        logger.info("=" * 60)


# ================================================================
# 模块入口（可单独运行）
# ================================================================
if __name__ == "__main__":
    spider = JobSpider()
    spider.run()
