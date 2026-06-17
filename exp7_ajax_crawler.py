# -*- coding: utf-8 -*-
"""
实验七：动态网页数据爬取实战 —— Ajax 接口分页爬取
目标网站：Bilibili 热门视频榜单
接口地址：https://api.bilibili.com/x/web-interface/popular
功能：通过抓取 Ajax 接口，分页爬取 B 站热门视频数据，保存为 CSV 文件
"""

import requests
import json
import csv
import time
import random
import os
from datetime import datetime


def get_headers():
    """
    构造请求头，模拟浏览器访问
    Referer 设为 B 站首页，避免基础反爬拦截
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    return headers


def fetch_page(api_url, params, headers, max_retries=3):
    """
    发送 HTTP 请求获取 Ajax 接口 JSON 数据

    Args:
        api_url: 接口 URL
        params: 请求参数（含分页参数）
        headers: 请求头（模拟浏览器）
        max_retries: 最大重试次数

    Returns:
        dict: JSON 响应数据，失败返回 None
    """
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(
                api_url,
                params=params,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            response.encoding = "utf-8"

            # 解析 JSON 数据
            json_data = response.json()

            # B 站 API 返回 code=0 表示成功
            if json_data.get("code") == 0:
                return json_data
            else:
                print(f"  [API错误] code={json_data.get('code')}, "
                      f"message={json_data.get('message')}")
                return None

        except requests.exceptions.Timeout:
            print(f"  [超时] 第 {attempt} 次请求超时")
        except requests.exceptions.HTTPError as e:
            print(f"  [HTTP错误] 第 {attempt} 次: {e.response.status_code}")
            if e.response.status_code == 412:
                print("  [提示] 412 错误，可能是反爬拦截，增加延时...")
        except json.JSONDecodeError:
            print(f"  [解析错误] 第 {attempt} 次: 响应不是合法 JSON")
        except Exception as e:
            print(f"  [未知错误] 第 {attempt} 次: {e}")

        # 重试前等待（指数退避）
        if attempt < max_retries:
            wait = random.uniform(2, 5) * attempt
            print(f"  [等待] {wait:.1f}s 后重试...")
            time.sleep(wait)

    return None


def parse_data(json_data):
    """
    解析 API 返回的 JSON 数据，提取视频信息

    B站热门接口返回结构：
    {
        "code": 0,
        "data": {
            "list": [
                {
                    "title": "视频标题",
                    "bvid": "BVxxxxxx",
                    "owner": {"name": "作者", "mid": 123},
                    "stat": {"view": 100, "danmaku": 10, "like": 50, ...},
                    "tname": "分区名",
                    ...
                }
            ],
            "no_more": false
        }
    }

    Args:
        json_data: API 返回的 JSON 数据

    Returns:
        (video_list, has_more): 视频信息列表和是否有更多数据
    """
    video_list = []

    if not json_data or not isinstance(json_data, dict):
        return video_list, False

    data = json_data.get("data", {})
    videos = data.get("list", [])

    for item in videos:
        try:
            # 提取视频标题
            title = item.get("title", "无标题")

            # 提取 BV 号和视频链接
            bvid = item.get("bvid", "")
            video_url = f"https://www.bilibili.com/video/{bvid}" if bvid else ""

            # 提取作者信息
            owner = item.get("owner", {})
            author = owner.get("name", "未知作者")

            # 提取统计数据
            stat = item.get("stat", {})
            view_count = stat.get("view", 0)      # 播放量
            danmaku_count = stat.get("danmaku", 0) # 弹幕数
            like_count = stat.get("like", 0)       # 点赞数

            # 提取分区名称
            tname = item.get("tname", "未知分区")

            # 提取发布时间（时间戳转日期）
            pubdate = item.get("pubdate", 0)
            if pubdate:
                pub_time = datetime.fromtimestamp(pubdate).strftime("%Y-%m-%d")
            else:
                pub_time = "未知"

            video_info = {
                "序号": len(video_list) + 1,
                "标题": title,
                "BV号": bvid,
                "链接": video_url,
                "作者": author,
                "分区": tname,
                "播放量": view_count,
                "弹幕数": danmaku_count,
                "点赞数": like_count,
                "发布日期": pub_time,
            }
            video_list.append(video_info)

        except Exception as e:
            print(f"  [警告] 解析单条数据失败: {e}")
            continue

    # B站热门接口每次返回50条，no_more 标识是否还有更多
    no_more = data.get("no_more", True)
    has_more = not no_more

    return video_list, has_more


def save_to_csv(video_list, filename="bilibili_popular.csv"):
    """
    将视频数据保存到 CSV 文件（UTF-8-BOM 编码，兼容 Excel）

    Args:
        video_list: 视频数据列表
        filename: 输出文件名
    """
    if not video_list:
        print("[警告] 没有数据可保存")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(script_dir, filename)

    fieldnames = ["序号", "标题", "BV号", "链接", "作者",
                  "分区", "播放量", "弹幕数", "点赞数", "发布日期"]

    try:
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(video_list)
        print(f"\n[保存成功] {len(video_list)} 条数据已保存到 {filepath}")
    except PermissionError:
        print(f"[错误] 文件被占用: {filepath}")
    except Exception as e:
        print(f"[错误] 保存失败: {e}")


def main():
    """
    主函数：Ajax 接口分页爬取 B 站热门视频
    """
    print("=" * 60)
    print("  实验七 - Ajax 接口分页爬取")
    print("  目标：Bilibili 热门视频榜单")
    print(f"  开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # ---------- 配置参数 ----------
    # Bilibili 热门视频 API（通过开发者工具 Network 面板抓取获得）
    api_url = "https://api.bilibili.com/x/web-interface/popular"

    # 接口参数说明：
    #   pn: 页码（从 1 开始）
    #   ps: 每页条数（50 为上限）
    params_base = {
        "pn": 1,
        "ps": 20,  # 每页 20 条
    }

    headers = get_headers()
    all_videos = []
    target_pages = 3  # 目标爬取 3 页
    page = 1

    print(f"\n[目标] 爬取 {target_pages} 页，每页 20 条")
    print(f"[接口] {api_url}")
    print(f"[请求方式] GET")
    print(f"[数据格式] JSON")
    print("-" * 60)

    # ---------- 分页爬取 ----------
    while page <= target_pages:
        print(f"\n>>> 第 {page} 页 <<<")

        # 构造当前页的请求参数
        params = params_base.copy()
        params["pn"] = page

        # ① 发送 HTTP 请求，获取 JSON 数据
        print(f"  [请求] GET {api_url}?pn={page}&ps=20")
        json_data = fetch_page(api_url, params, headers)

        if json_data is None:
            print(f"  [失败] 第 {page} 页获取失败，跳过")
            page += 1
            continue

        # ② 解析 JSON 数据，提取目标字段
        videos, has_more = parse_data(json_data)

        if not videos:
            print(f"  [空数据] 第 {page} 页无数据")
            break

        # ③ 序号修正（跨页连续编号）
        for v in videos:
            v["序号"] = len(all_videos) + 1
        all_videos.extend(videos)

        print(f"  [成功] 本页提取 {len(videos)} 条视频")
        print(f"  [累计] 共 {len(all_videos)} 条")

        # 检查是否有更多数据
        if not has_more or page >= target_pages:
            break

        page += 1

        # 随机延时（模拟人类浏览行为，降低请求频率）
        if page <= target_pages:
            delay = random.uniform(2, 4)
            print(f"  [延时] {delay:.1f}s 后请求下一页...")
            time.sleep(delay)

    # ---------- 保存结果 ----------
    print("\n" + "=" * 60)
    print("  爬取完成，保存数据...")
    print("=" * 60)

    save_to_csv(all_videos, "bilibili_popular.csv")

    # ---------- 数据预览 ----------
    if all_videos:
        print("\n" + "-" * 60)
        print("  数据预览（前 5 条）")
        print("-" * 60)
        for v in all_videos[:5]:
            print(f"  {v['序号']:2d}. {v['标题'][:40]}")
            print(f"      作者: {v['作者']:12s} | 播放: {v['播放量']:>8d} | "
                  f"点赞: {v['点赞数']:>6d} | {v['发布日期']}")

    # ---------- 统计信息 ----------
    print("\n" + "=" * 60)
    print("  爬取统计")
    print("=" * 60)
    print(f"  总爬取页数: {page}")
    print(f"  总视频条数: {len(all_videos)}")
    print(f"  数据文件:   bilibili_popular.csv")
    print(f"  结束时间:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
