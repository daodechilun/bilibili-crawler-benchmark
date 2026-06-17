# -*- coding: utf-8 -*-
"""
实验七：动态网页数据爬取实战 —— Selenium 自动化爬取
目标网站：Bilibili 热门视频页面（JS 动态渲染）
功能：使用 Selenium 模拟浏览器加载页面，结合显式等待提取动态渲染的视频数据
"""

import csv
import time
import os
import sys
from datetime import datetime

# ---------- Selenium 相关导入 ----------
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)


def create_driver():
    """
    初始化 Chrome 浏览器驱动

    配置说明：
    - 禁用自动化检测标志（避免被网站识别为自动化工具）
    - 设置窗口大小（确保页面元素完整加载）
    - 使用 webdriver-manager 自动匹配 Chrome 驱动版本

    Returns:
        WebDriver 实例
    """
    print("[初始化] 正在启动 Chrome 浏览器...")

    options = Options()

    # 基础配置
    options.add_argument("--window-size=1920,1080")          # 窗口大小
    options.add_argument("--disable-blink-features=AutomationControlled")  # 隐藏自动化标志
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # 可选：无头模式（生产环境建议开启，调试阶段保持有头模式以便截图）
    # options.add_argument("--headless=new")

    # 禁用 GPU 和沙箱（解决部分 Windows 环境兼容性问题）
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # 禁用弹窗和通知
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_settings.popups": 0,
    }
    options.add_experimental_option("prefs", prefs)

    try:
        # 优先使用项目目录下的本地 ChromeDriver
        local_driver = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chromedriver.exe")
        if os.path.exists(local_driver):
            service = Service(local_driver)
            print("[驱动] 使用本地 ChromeDriver")
        else:
            # 备选：尝试 webdriver-manager
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
                print("[驱动] 使用 webdriver-manager 自动管理 ChromeDriver")
            except (ImportError, Exception):
                service = Service()
                print("[驱动] 从系统 PATH 查找 ChromeDriver")

        driver = webdriver.Chrome(service=service, options=options)

        # 执行 CDP 命令隐藏 webdriver 属性
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        print("[成功] 浏览器启动完成\n")
        return driver

    except WebDriverException as e:
        print(f"[错误] 浏览器启动失败: {e}")
        print("[提示] 请确保：")
        print("  1. Chrome 浏览器已安装")
        print("  2. ChromeDriver 版本与 Chrome 版本匹配")
        print("  3. 或运行: pip install webdriver-manager")
        sys.exit(1)


def wait_and_get_elements(driver, wait, by, selector, timeout_msg):
    """
    使用显式等待获取页面动态元素

    显式等待原理：
    - 持续检测目标元素是否出现（最长等待指定时间）
    - 元素就绪后立即返回，无需等待整个等待时长
    - 超时则抛出 TimeoutException

    Args:
        driver: WebDriver 实例
        wait: WebDriverWait 实例
        by: 元素定位方式 (By.CSS_SELECTOR, By.XPATH 等)
        selector: 元素选择器
        timeout_msg: 超时提示信息

    Returns:
        list: 定位到的元素列表
    """
    try:
        elements = wait.until(
            EC.presence_of_all_elements_located((by, selector))
        )
        return elements
    except TimeoutException:
        print(f"  [超时] {timeout_msg}")
        return []


def scroll_to_bottom(driver, times=2):
    """
    模拟滚动页面到底部，触发懒加载内容

    Args:
        driver: WebDriver 实例
        times: 滚动次数
    """
    for i in range(times):
        driver.execute_script(
            "window.scrollTo(0, document.documentElement.scrollHeight);"
        )
        time.sleep(1.5)  # 等待内容加载
        # 滚动回一点，触发更多加载
        driver.execute_script(
            "window.scrollBy(0, -200);"
        )
        time.sleep(0.5)


def extract_video_data(driver, cards):
    """
    从视频卡片元素中提取数据

    Bilibili 热门页面实际卡片结构：
    - 卡片容器: div.video-card
      - div.video-card__content
        - a (视频链接, href 为 BV 链接)
        - div.video-card__info
          - p.video-name (标题, text 和 title 属性)
          - span.up-name (作者名)
          - div 中的文本包含播放量等信息

    Args:
        driver: WebDriver 实例
        cards: 视频卡片 WebElement 列表

    Returns:
        list[dict]: 提取的视频数据列表
    """
    video_list = []

    for card in cards:
        try:
            # 提取标题 - B站使用 p.video-name
            title = ""
            try:
                title_el = card.find_element(By.CSS_SELECTOR, ".video-name")
                title = title_el.get_attribute("title") or title_el.text.strip()
            except NoSuchElementException:
                # 备选：直接搜索所有链接和文本
                try:
                    links = card.find_elements(By.CSS_SELECTOR, "a")
                    for a in links:
                        t = a.get_attribute("title") or a.text.strip()
                        if t and len(t) > 2:
                            title = t
                            break
                except Exception:
                    pass

            if not title:
                continue  # 无标题则跳过该卡片

            # 提取视频链接
            link = ""
            try:
                link_el = card.find_element(By.CSS_SELECTOR, ".video-card__content > a")
                link = link_el.get_attribute("href") or ""
            except NoSuchElementException:
                try:
                    link_el = card.find_element(By.CSS_SELECTOR, "a")
                    link = link_el.get_attribute("href") or ""
                except NoSuchElementException:
                    pass

            # 提取作者 - B站使用 span.up-name
            author = "未知"
            try:
                author_el = card.find_element(By.CSS_SELECTOR, ".up-name")
                author = author_el.text.strip()
            except NoSuchElementException:
                pass

            # 提取播放量和弹幕数
            # B站热门卡片的播放量在 .video-card__info 内，没有单独的 class
            play_count = "0"
            danmaku_count = "0"
            try:
                info_div = card.find_element(By.CSS_SELECTOR, ".video-card__info")
                # 获取整个 info_div 的文本，过滤掉标题和作者
                full_text = info_div.text
                lines = full_text.split("\n")

                # 标题通常在 video-name 里，需要排除
                title_text = ""
                try:
                    title_text = info_div.find_element(By.CSS_SELECTOR, ".video-name").text.strip()
                except NoSuchElementException:
                    pass

                # 作者名
                author_text = ""
                try:
                    author_text = info_div.find_element(By.CSS_SELECTOR, ".up-name").text.strip()
                except NoSuchElementException:
                    pass

                # 标签文本（如"百万播放"）
                tag_text = ""
                try:
                    tag_text = info_div.find_element(By.CSS_SELECTOR, ".rcmd-tag").text.strip()
                except NoSuchElementException:
                    pass

                # 从文本行中提取播放量和弹幕数
                # 播放量特征：包含"万"的数字
                # 弹幕数特征：纯数字或包含"万"
                numeric_lines = []
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    # 排除标题、作者、标签
                    if line == title_text or line == author_text or line == tag_text:
                        continue
                    numeric_lines.append(line)

                # 最后两个数字行通常是播放量和弹幕数
                if len(numeric_lines) >= 2:
                    play_count = numeric_lines[-2]  # 倒数第二是播放量
                    danmaku_count = numeric_lines[-1]  # 最后是弹幕/评论
                elif len(numeric_lines) == 1:
                    play_count = numeric_lines[0]

            except NoSuchElementException:
                pass

            video_info = {
                "序号": len(video_list) + 1,
                "标题": title,
                "链接": link,
                "作者": author,
                "播放量": play_count,
                "弹幕数": danmaku_count,
            }
            video_list.append(video_info)

        except StaleElementReferenceException:
            print("  [警告] 元素已失效，跳过")
            continue
        except Exception as e:
            print(f"  [警告] 提取单条数据失败: {e}")
            continue

    return video_list


def save_to_csv(video_list, filename="bilibili_selenium.csv"):
    """
    保存视频数据到 CSV 文件（UTF-8-BOM 编码）
    """
    if not video_list:
        print("[警告] 没有数据可保存")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(script_dir, filename)

    fieldnames = ["序号", "标题", "链接", "作者", "播放量", "弹幕数"]

    try:
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(video_list)
        print(f"\n[保存成功] {len(video_list)} 条数据已保存到 {filepath}")
    except Exception as e:
        print(f"[错误] 保存失败: {e}")


def main():
    """
    主函数：Selenium 自动化爬取流程

    流程说明：
    1. 初始化 Chrome 浏览器驱动
    2. 配置显式等待（最大等待 10 秒）
    3. 打开 Bilibili 热门页面
    4. 等待视频卡片元素加载完成
    5. 滚动页面触发更多内容加载
    6. 提取视频数据
    7. 模拟翻页操作（滚动加载更多）
    8. 保存数据并关闭浏览器
    """
    print("=" * 60)
    print("  实验七 - Selenium 动态渲染爬取")
    print("  目标：Bilibili 热门视频页面（JS 动态渲染）")
    print(f"  开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    driver = None
    all_videos = []
    target_pages = 3  # 爬取 3 页（3 次滚动加载）

    try:
        # ---------- ① 初始化浏览器 ----------
        driver = create_driver()

        # ---------- ② 配置显式等待 ----------
        # 最大等待 10 秒，每 0.5 秒检查一次
        wait = WebDriverWait(driver, 10, poll_frequency=0.5)

        # ---------- ③ 打开目标动态网页 ----------
        url = "https://www.bilibili.com/v/popular/all"
        print(f"[导航] 正在打开：{url}")
        driver.get(url)

        # 等待页面基础框架加载
        time.sleep(2)

        print("[等待] 等待动态元素加载...")

        # ---------- ④ 循环爬取多页 ----------
        for page in range(1, target_pages + 1):
            print(f"\n{'=' * 60}")
            print(f"  第 {page} 页 —— 等待 JS 渲染并提取数据")
            print(f"{'=' * 60}")

            # 显式等待：等待视频卡片容器加载完成
            # 尝试多种可能的 CSS 选择器（提高兼容性）
            # Bilibili 热门页面实际使用 .video-card 作为卡片容器
            cards = wait_and_get_elements(
                driver, wait,
                By.CSS_SELECTOR,
                ".video-card",
                "视频卡片未在 10 秒内加载完成"
            )

            if not cards:
                # 尝试备选选择器
                print("  [备选] 尝试通用选择器...")
                cards = driver.find_elements(
                    By.CSS_SELECTOR,
                    "[class*='video-card'], .card-wrap"
                )
                if not cards:
                    print("  [警告] 未找到视频元素，尝试继续滚动...")

            if cards:
                print(f"  [定位] 找到 {len(cards)} 个视频卡片元素")

                # 提取当前页数据
                page_videos = extract_video_data(driver, cards)
                for v in page_videos:
                    v["序号"] = len(all_videos) + 1
                all_videos.extend(page_videos)
                print(f"  [提取] 本页提取 {len(page_videos)} 条数据")
                print(f"  [累计] 共 {len(all_videos)} 条")

            # 滚动页面加载更多内容
            if page < target_pages:
                print(f"\n  [滚动] 滚动页面加载更多视频...")
                scroll_to_bottom(driver, times=2)
                # 等待新内容渲染
                time.sleep(2)

        # ---------- ⑤ 保存数据 ----------
        print("\n" + "=" * 60)
        print("  爬取完成，保存数据...")
        print("=" * 60)
        save_to_csv(all_videos, "bilibili_selenium.csv")

        # ---------- ⑥ 数据预览 ----------
        if all_videos:
            print("\n" + "-" * 60)
            print("  数据预览（前 5 条）")
            print("-" * 60)
            for v in all_videos[:5]:
                # 安全处理可能含特殊字符的标题
                safe_title = v['标题'][:45].encode('gbk', errors='replace').decode('gbk', errors='replace')
                safe_author = v['作者'].encode('gbk', errors='replace').decode('gbk', errors='replace')
                print(f"  {v['序号']:2d}. {safe_title}")
                print(f"      作者: {safe_author:12s} | 播放: {v['播放量']} | "
                      f"弹幕: {v['弹幕数']}")

        # ---------- ⑦ 统计 ----------
        print("\n" + "=" * 60)
        print("  爬取统计")
        print("=" * 60)
        print(f"  总爬取页数: {target_pages}")
        print(f"  总视频条数: {len(all_videos)}")
        print(f"  数据文件:   bilibili_selenium.csv")
        print(f"  结束时间:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

    except WebDriverException as e:
        print(f"\n[严重错误] 浏览器异常: {e}")
    except KeyboardInterrupt:
        print("\n[用户中断] 收到退出信号")
    except Exception as e:
        print(f"\n[未知错误] {e}")
        import traceback
        traceback.print_exc()
    finally:
        # ---------- ⑧ 关闭浏览器，释放资源 ----------
        if driver:
            print("\n[清理] 正在关闭浏览器...")
            try:
                driver.quit()
                print("[清理] 浏览器已关闭，资源已释放")
            except Exception:
                pass


if __name__ == "__main__":
    main()
