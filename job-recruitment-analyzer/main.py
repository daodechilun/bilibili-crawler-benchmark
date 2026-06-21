"""
项目主入口 —— 一键启动
=======================

使用方式（在终端里输入）：
  python main.py crawl      → 启动数据采集
  python main.py clean      → 运行数据清洗
  python main.py analyze    → 跑数据分析+ML
  python main.py visualize  → 启动Flask可视化界面
  python main.py report     → 生成Word报告+PPT
  python main.py all        → 一键跑通全流程

如果你只想跑某个环节，用对应的命令就行。
"""
import sys
import os

# 把项目根目录加入Python搜索路径（确保模块导入正常）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config


def cmd_crawl():
    """命令: crawl —— 启动数据采集"""
    print("\n" + "▓" * 50)
    print("  阶段1: 数据采集")
    print("  从51job抓取IT岗位数据 → 保存为 raw_data.csv")
    print("  使用 stealth 浏览器方案绕过 WAF")
    print("▓" * 50 + "\n")

    from crawler.live_spider import LiveSpider
    spider = LiveSpider(headless=True)
    spider.run()


def cmd_clean():
    """命令: clean —— 运行数据清洗"""
    print("\n" + "▓" * 50)
    print("  阶段2: 数据清洗")
    print("  清洗 raw_data.csv → 入库 MySQL → 输出 cleaned_data.csv")
    print("▓" * 50 + "\n")

    from cleaner.cleaner import DataCleaner
    cleaner = DataCleaner()
    cleaner.run()


def cmd_analyze():
    """命令: analyze —— 跑数据分析+ML建模"""
    print("\n" + "▓" * 50)
    print("  阶段3: 数据分析与机器学习")
    print("  描述性统计 + 薪资预测回归 + KMeans聚类")
    print("▓" * 50 + "\n")

    from analysis.statistics import StatisticsAnalyzer
    from analysis.salary_predict import SalaryPredictor
    from analysis.clustering import JobClusterer

    # Step 1: 描述性统计
    print("\n📊 [1/3] 描述性统计分析")
    stats = StatisticsAnalyzer()
    stats.run()

    # Step 2: 薪资预测
    print("\n💰 [2/3] 薪资预测回归")
    predictor = SalaryPredictor()
    predictor.run()

    # Step 3: 岗位聚类
    print("\n🔮 [3/3] KMeans岗位聚类")
    clusterer = JobClusterer()
    clusterer.run()

    print("\n✅ 阶段3全部完成！")


def cmd_visualize():
    """命令: visualize —— 启动Flask可视化"""
    print("\n" + "▓" * 50)
    print("  阶段4: 可视化系统")
    print(f"  启动Flask → 浏览器打开 http://127.0.0.1:5000")
    print("▓" * 50 + "\n")

    from visualization.app import app
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG)


def cmd_report():
    """命令: report —— 生成Word报告+PPT"""
    import subprocess

    print("\n" + "▓" * 50)
    print("  阶段5: 生成报告与PPT")
    print("  输出: output/report.docx + output/presentation.pptx")
    print("▓" * 50 + "\n")

    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

    # Word报告（Node.js - docx-js）
    print("📝 生成Word报告...")
    report_js = os.path.join(output_dir, "generate_report.js")
    try:
        result = subprocess.run(
            ["node", report_js],
            cwd=os.path.dirname(report_js),
            capture_output=True, text=True, timeout=30,
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
    except FileNotFoundError:
        print("⚠️ 未安装Node.js或找不到node命令")
        print("   请安装Node.js后运行: npm install -g docx")
        print(f"   然后手动运行: node {report_js}")
    except Exception as e:
        print(f"⚠️ Word报告生成失败: {e}")

    # PPT（Node.js - pptxgenjs）
    print("\n📊 生成答辩PPT...")
    ppt_js = os.path.join(output_dir, "generate_ppt.js")
    try:
        result = subprocess.run(
            ["node", ppt_js],
            cwd=os.path.dirname(ppt_js),
            capture_output=True, text=True, timeout=30,
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
    except FileNotFoundError:
        print("⚠️ 未安装Node.js或找不到node命令")
        print("   请安装Node.js后运行: npm install -g pptxgenjs")
        print(f"   然后手动运行: node {ppt_js}")
    except Exception as e:
        print(f"⚠️ PPT生成失败: {e}")

    # 检查输出
    report_path = os.path.join(output_dir, "report.docx")
    ppt_path = os.path.join(output_dir, "presentation.pptx")
    if os.path.exists(report_path):
        print(f"\n✅ Word报告: {report_path}")
    if os.path.exists(ppt_path):
        print(f"✅ 答辩PPT: {ppt_path}")


def cmd_all():
    """命令: all —— 一键跑通全流程"""
    print("\n" + "▓" * 60)
    print("  🚀 一键运行全部5个阶段")
    print("▓" * 60)
    cmd_crawl()
    cmd_clean()
    cmd_analyze()
    cmd_visualize()
    cmd_report()


def print_usage():
    """打印使用说明"""
    print("""
╔══════════════════════════════════════════════════╗
║    IT岗位招聘数据分析 — 课程大作业              ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  用法: python main.py <命令>                    ║
║                                                  ║
║  可用命令:                                       ║
║    crawl     → 爬取51job数据 → raw_data.csv     ║
║    clean     → 清洗数据 → MySQL + cleaned.csv   ║
║    analyze   → 分析+ML → 结果JSON + 图表        ║
║    visualize → 启动Flask可视化 (端口5000)       ║
║    report    → 生成Word报告 + 答辩PPT           ║
║    all       → 一键跑通全部流程                  ║
║                                                  ║
║  示例:                                           ║
║    python main.py crawl                          ║
║    python main.py analyze                        ║
║    python main.py all                            ║
║                                                  ║
╚══════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(0)

    cmd = sys.argv[1].lower().strip()

    commands = {
        "crawl": cmd_crawl,
        "clean": cmd_clean,
        "analyze": cmd_analyze,
        "visualize": cmd_visualize,
        "report": cmd_report,
        "all": cmd_all,
    }

    if cmd in commands:
        commands[cmd]()
    else:
        print(f"❌ 未知命令: {cmd}")
        print_usage()
