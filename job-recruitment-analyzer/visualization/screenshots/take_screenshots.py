"""截图脚本：对 mockup.html 进行深色/浅色两种主题的全页截图"""
from playwright.sync_api import sync_playwright
import os

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
URL = "http://127.0.0.1:8765/mockup.html"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    print("[1/4] 打开页面...")
    page.goto(URL, timeout=30000)
    page.wait_for_load_state("networkidle")
    # 等 ECharts 图表渲染完成
    page.wait_for_timeout(3000)
    # 滚动到底部触发所有图表渲染
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1000)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(500)

    # ===== 截图1：深色主题全页 =====
    print("[2/4] 截图：深色科技大屏（全页）...")
    path1 = os.path.join(OUTPUT_DIR, "01_深色主题_全页.png")
    page.screenshot(path=path1, full_page=True)
    print(f"  已保存: {path1}")

    # ===== 深色主题分段截图（方便放PPT） =====
    print("[2b/4] 截图：深色主题关键区块...")

    # KPI 看板
    kpi = page.locator(".kpi-row")
    if kpi.count() > 0:
        kpi.first.screenshot(path=os.path.join(OUTPUT_DIR, "02_KPI数字看板.png"))
        print("  已保存: KPI数字看板")

    # 图表网格整体
    chart_grid = page.locator(".chart-grid")
    if chart_grid.count() > 0:
        chart_grid.first.screenshot(path=os.path.join(OUTPUT_DIR, "03_图表网格总览.png"))
        print("  已保存: 图表网格总览")

    # ===== 切换到浅色主题 =====
    print("[3/4] 切换到浅色主题...")
    light_btn = page.locator("#btnLight")
    light_btn.click()
    page.wait_for_timeout(1000)

    # 滚动触发重新渲染
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(500)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(500)

    # ===== 截图4：浅色主题全页 =====
    print("[4/4] 截图：浅色商务报告（全页）...")
    path4 = os.path.join(OUTPUT_DIR, "04_浅色主题_全页.png")
    page.screenshot(path=path4, full_page=True)
    print(f"  已保存: {path4}")

    # 浅色主题分段
    print("[4b/4] 截图：浅色主题关键区块...")
    kpi_light = page.locator(".kpi-row")
    if kpi_light.count() > 0:
        kpi_light.first.screenshot(path=os.path.join(OUTPUT_DIR, "05_KPI看板_浅色.png"))
        print("  已保存: KPI看板_浅色")

    chart_grid_light = page.locator(".chart-grid")
    if chart_grid_light.count() > 0:
        chart_grid_light.first.screenshot(path=os.path.join(OUTPUT_DIR, "06_图表网格_浅色.png"))
        print("  已保存: 图表网格_浅色")

    browser.close()
    print("\n✅ 全部截图完成！")
