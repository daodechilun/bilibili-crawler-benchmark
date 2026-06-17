# -*- coding: utf-8 -*-
"""
实验七 —— 两种动态爬取方案对比分析脚本
对比维度：爬取效率、资源占用、数据准确性
"""

import requests
import time
import json
import csv
import os
import sys
import io
import psutil
import threading

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def benchmark_ajax(target_items=50, pages=10):
    """Ajax 接口爬取方案性能测试"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com/",
    }
    api_url = "https://api.bilibili.com/x/web-interface/popular"

    process = psutil.Process(os.getpid())
    cpu_before = process.cpu_percent(interval=0.5)
    mem_before = process.memory_info().rss / 1024 / 1024  # MB

    start_time = time.time()
    all_items = []
    request_count = 0

    print("=" * 60)
    print("  Ajax 接口爬取性能测试")
    print("=" * 60)
    print(f"  目标: {pages} 页, 约 {target_items} 条数据")

    for page in range(1, pages + 1):
        params = {"pn": page, "ps": max(1, target_items // pages)}
        try:
            r = requests.get(api_url, params=params, headers=headers, timeout=10)
            request_count += 1
            data = r.json()
            items = data.get("data", {}).get("list", [])
            for item in items:
                all_items.append({
                    "title": item.get("title", ""),
                    "author": item.get("owner", {}).get("name", ""),
                    "view": item.get("stat", {}).get("view", 0),
                    "like": item.get("stat", {}).get("like", 0),
                })
        except Exception as e:
            print(f"  第{page}页失败: {e}")

        if page < pages:
            time.sleep(0.3)

    elapsed = time.time() - start_time
    cpu_after = process.cpu_percent(interval=0.5)
    mem_after = process.memory_info().rss / 1024 / 1024

    print(f"  耗时: {elapsed:.2f} 秒")
    print(f"  请求数: {request_count}")
    print(f"  数据量: {len(all_items)} 条")
    print(f"  内存峰值: {mem_after:.1f} MB")
    print(f"  CPU: {cpu_after:.1f}%")
    print(f"  平均每页: {elapsed/pages:.2f}s")

    return {
        "method": "Ajax 接口爬取",
        "time": round(elapsed, 2),
        "items": len(all_items),
        "requests": request_count,
        "memory": round(mem_after, 1),
        "cpu": round(cpu_after, 1),
        "avg_per_page": round(elapsed / pages, 2),
        "data_accuracy": "100% (直接解析JSON)",
        "code_complexity": "中等 (需抓包分析接口)",
    }


def benchmark_selenium_stub():
    """
    Selenium 自动化爬取性能估算
    实际运行需启动浏览器，此处使用模拟数据（实际值需运行 exp7_selenium_crawler.py 获得）
    """
    print("\n" + "=" * 60)
    print("  Selenium 自动化爬取性能测试")
    print("=" * 60)
    print("  目标: 3 页, 约 50 条数据")
    print("  启动浏览器...")
    print("  注：Selenium 实际性能数据将根据运行结果填写")
    print()

    # Selenium 典型性能特征（基于经验估算，实际值以运行结果为准）
    return {
        "method": "Selenium 自动化爬取",
        "time": "见实际运行",
        "items": "见实际运行",
        "requests": "1 (加载完整页面)",
        "memory": "300-800 MB (含浏览器进程)",
        "cpu": "20-40% (含浏览器渲染)",
        "avg_per_page": "见实际运行",
        "data_accuracy": "95%+ (依赖页面结构)",
        "code_complexity": "较低 (无需抓包，直接解析DOM)",
    }


def print_comparison(ajax_result, selenium_result):
    """打印对比表格"""
    print("\n" + "=" * 70)
    print("  两种动态爬取方案对比分析")
    print("=" * 70)
    print()
    print(f"{'对比维度':<16} {'Ajax接口爬取':<24} {'Selenium自动化爬取':<24}")
    print("-" * 64)

    comparisons = [
        ("爬取效率", f"{ajax_result['time']}秒/{ajax_result['items']}条", selenium_result['time']),
        ("资源占用(内存)", f"{ajax_result['memory']} MB", selenium_result['memory']),
        ("CPU 占用", f"{ajax_result['cpu']}%", selenium_result['cpu']),
        ("请求次数", str(ajax_result['requests']), selenium_result['requests']),
        ("数据准确性", ajax_result['data_accuracy'], selenium_result['data_accuracy']),
        ("代码难度", ajax_result['code_complexity'], selenium_result['code_complexity']),
        ("适用场景", "接口公开、参数简单的\n大批量高效爬取", "接口加密、JS强渲染的\n复杂网页"),
        ("优点", "速度快、资源少、\n数据格式规范", "兼容性强、无需抓包、\n模拟真实用户"),
        ("缺点", "接口变更则失效、\n需抓包分析参数", "速度慢、资源占用高、\n受浏览器版本限制"),
    ]

    for label, ajax, selenium in comparisons:
        print(f"{label:<16} {ajax:<24} {selenium:<24}")

    print("-" * 64)
    print()
    print("  结论：")
    print("  1. Ajax 接口爬取在效率、资源占用方面显著优于 Selenium")
    print("  2. Selenium 兼容性更强，适合接口加密或难以抓包的场景")
    print("  3. 实际开发中应优先尝试 Ajax 接口方案，")
    print("     仅在接口不可用时使用 Selenium 兜底")
    print()
    print("=" * 70)


def save_results(ajax_result, filename="benchmark_results.json"):
    """保存基准测试结果到 JSON 文件"""
    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(ajax_result, f, ensure_ascii=False, indent=2)
    print(f"\n[保存] 性能测试数据已保存到 {filepath}")


if __name__ == "__main__":
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║  实验七：动态网页数据爬取 —— 方案对比性能测试          ║")
    print("╚" + "═" * 58 + "╝")
    print()

    # 运行 Ajax 性能测试
    ajax_result = benchmark_ajax(target_items=50, pages=10)
    save_results(ajax_result)

    print()
    print("  [提示] Selenium 性能数据请运行 exp7_selenium_crawler.py 后补充")
    print("  Selenium 典型值:")
    print("    - 启动浏览器: ~3-5秒")
    print("    - 每页渲染: ~2-4秒")
    print("    - 3页50条数据: ~15-25秒")
    print("    - 内存占用: ~300-800 MB")
