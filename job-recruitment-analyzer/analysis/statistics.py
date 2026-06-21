"""
描述性统计分析
=============
从 cleaned_data.csv 加载数据，计算关键维度的统计指标，
输出 JSON 文件供 Flask 可视化接口直接读取。

分析维度：
1. 城市薪资深浅排行榜
2. 学历-薪资分布（盒须图数据）
3. 经验-薪资关系
4. Top20 技能词频
5. 行业薪资对比
6. 岗位发布时间趋势

所有结果保存到 analysis/ 目录，JSON 格式。
"""
import os
import json
from collections import Counter
from typing import Dict, List

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # 非交互模式（服务器/无GUI环境下也能用）
import matplotlib.pyplot as plt
from loguru import logger

import config


# 中文字体设置（Windows用SimHei, Mac用PingFang）
plt.rcParams["font.sans-serif"] = ["SimHei", "PingFang SC", "WenQuanYi Micro Hei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题


class StatisticsAnalyzer:
    """
    描述性统计器
    -----------
    加载清洗数据 → 分维度统计 → 输出JSON + 静态图表

    用法：
        analyzer = StatisticsAnalyzer()
        analyzer.run()
    """

    def __init__(self):
        self.cleaned_path = os.path.join(config.CLEANED_DIR, "cleaned_data.csv")
        self.output_dir = os.path.dirname(os.path.abspath(__file__))
        self.chart_dir = os.path.join(config.CHART_DIR)
        self.df = None
        self.results = {}  # 存放所有分析结果

    def run(self):
        """一键运行全部分析"""
        logger.info("=" * 60)
        logger.info("📊 描述性统计分析启动")
        logger.info("=" * 60)

        self._load()
        self._city_salary_ranking()
        self._education_salary()
        self._experience_salary()
        self._skill_top20()
        self._industry_salary()
        self._publish_trend()

        # 保存全部结果
        self._save_all()

        logger.info("✅ 描述性统计分析完成")
        return self.results

    # ================================================================
    # 数据加载
    # ================================================================

    def _load(self):
        """加载清洗后的数据"""
        if not os.path.exists(self.cleaned_path):
            raise FileNotFoundError(f"找不到清洗后数据: {self.cleaned_path}")

        self.df = pd.read_csv(self.cleaned_path, encoding="utf-8-sig")
        logger.info(f"📂 加载清洗数据: {len(self.df)} 条")

        # 薪资转数值
        for col in ["salary_avg", "salary_min", "salary_max", "exp_min", "exp_max"]:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors="coerce")

    # ================================================================
    # 1. 城市薪资深浅排行榜
    # ================================================================

    def _city_salary_ranking(self):
        """
        各城市岗位数量 + 平均薪资排行

        输出结构（给前端柱状图+折线图）：
        {
            "cities": ["北京", "上海", ...],
            "counts": [350, 280, ...],
            "avg_salaries": [25000, 22000, ...],
            "median_salaries": [23000, 21000, ...]
        }
        """
        logger.info("🏙️  分析: 城市薪资排行")

        city_stats = self.df.groupby("city").agg(
            count=("salary_avg", "count"),
            avg_salary=("salary_avg", "mean"),
            median_salary=("salary_avg", "median"),
            min_salary=("salary_avg", "min"),
            max_salary=("salary_avg", "max"),
        ).round(0)

        # 按平均薪资降序排列
        city_stats = city_stats.sort_values("avg_salary", ascending=False)

        result = {
            "cities": city_stats.index.tolist(),
            "counts": city_stats["count"].astype(int).tolist(),
            "avg_salaries": city_stats["avg_salary"].tolist(),
            "median_salaries": city_stats["median_salary"].tolist(),
        }
        self.results["salary_by_city"] = result
        self._save_json("salary_by_city.json", result)

        # 画图
        self._plot_bar(
            city_stats.head(15).index.tolist(),
            city_stats.head(15)["avg_salary"].tolist(),
            "各城市平均薪资排行 (Top15)",
            "city_salary_bar.png",
        )
        logger.info(f"   城市数: {len(city_stats)}, 最高薪资: {city_stats.index[0]}")

        return result

    # ================================================================
    # 2. 学历-薪资分布
    # ================================================================

    def _education_salary(self):
        """
        各学历段的薪资分布（盒须图数据 + 箱线图统计量）

        输出结构（给前端饼图/盒须图）：
        {
            "education": ["本科", "硕士", ...],
            "counts": [1200, 400, ...],
            "avg_salaries": [18000, 25000, ...],
            "q1": [...], "q3": [...], "median": [...]
        }
        """
        logger.info("🎓 分析: 学历-薪资分布")

        edu_order = ["不限", "大专", "本科", "硕士", "博士"]
        edu_stats = []

        for edu in edu_order:
            subset = self.df[self.df["education"] == edu]
            if len(subset) == 0:
                continue
            salaries = subset["salary_avg"].dropna()
            if len(salaries) == 0:
                continue
            edu_stats.append({
                "education": edu,
                "count": int(len(salaries)),
                "avg_salary": round(float(salaries.mean()), 0),
                "q1": round(float(salaries.quantile(0.25)), 0),
                "median": round(float(salaries.median()), 0),
                "q3": round(float(salaries.quantile(0.75)), 0),
            })

        result = {
            "education": [e["education"] for e in edu_stats],
            "counts": [e["count"] for e in edu_stats],
            "avg_salaries": [e["avg_salary"] for e in edu_stats],
            "q1": [e["q1"] for e in edu_stats],
            "median": [e["median"] for e in edu_stats],
            "q3": [e["q3"] for e in edu_stats],
        }
        self.results["salary_by_education"] = result
        self._save_json("salary_by_education.json", result)

        # 饼图：学历分布
        self._plot_pie(
            labels=result["education"],
            values=result["counts"],
            title="学历要求分布",
            filename="education_pie.png",
        )
        return result

    # ================================================================
    # 3. 经验-薪资关系
    # ================================================================

    def _experience_salary(self):
        """
        工作经验 vs 薪资（散点图/折线图数据）

        输出结构（给前端散点图）：
        {
            "exp_years": [0.5, 1, 2, 3, ...],
            "avg_salaries": [8000, 12000, 15000, ...],
            "counts": [50, 120, 200, ...]
        }
        """
        logger.info("📅 分析: 经验-薪资关系")

        # 按经验分段
        exp_bins = [0, 1, 2, 3, 5, 7, 10, 15, 100]
        exp_labels = ["0-1年", "1-2年", "2-3年", "3-5年", "5-7年", "7-10年", "10-15年", "15年+"]

        self.df["exp_bin"] = pd.cut(
            self.df["exp_min"], bins=exp_bins, labels=exp_labels, right=False
        )

        exp_stats = self.df.groupby("exp_bin", observed=False).agg(
            count=("salary_avg", "count"),
            avg_salary=("salary_avg", "mean"),
        ).round(0).dropna()

        result = {
            "exp_years": exp_stats.index.tolist(),
            "avg_salaries": exp_stats["avg_salary"].tolist(),
            "counts": exp_stats["count"].astype(int).tolist(),
        }
        self.results["salary_by_experience"] = result
        self._save_json("salary_by_experience.json", result)

        # 折线图
        self._plot_line(
            x=result["exp_years"],
            y=result["avg_salaries"],
            title="工作经验与薪资关系",
            xlabel="经验段",
            ylabel="平均月薪(元)",
            filename="experience_salary_line.png",
        )
        return result

    # ================================================================
    # 4. 🔥 Top20 技能词频
    # ================================================================

    def _skill_top20(self):
        """
        统计技能标签出现频率，输出 Top20

        方法：把所有岗位的 skill_tags 汇总，计数排序。

        输出结构（给前端词云/柱状图）：
        {
            "skills": ["Python", "SQL", "Java", ...],
            "counts": [850, 720, 500, ...],
            "avg_salaries": [20000, 18000, 22000, ...]
        }
        """
        logger.info("🏷️  分析: 技能热度 Top20")

        skill_counter = Counter()
        skill_salary_sum = {}
        skill_salary_count = {}

        for _, row in self.df.iterrows():
            tags = str(row.get("skill_tags", "")) if pd.notna(row.get("skill_tags")) else ""
            if not tags or tags == "nan":
                continue
            salary = row.get("salary_avg")
            for tag in tags.split(","):
                tag = tag.strip()
                if not tag:
                    continue
                skill_counter[tag] += 1
                if pd.notna(salary) and salary > 0:
                    skill_salary_sum[tag] = skill_salary_sum.get(tag, 0) + salary
                    skill_salary_count[tag] = skill_salary_count.get(tag, 0) + 1

        top20 = skill_counter.most_common(20)

        result = {
            "skills": [t[0] for t in top20],
            "counts": [t[1] for t in top20],
            "avg_salaries": [
                round(skill_salary_sum.get(t[0], 0) / skill_salary_count.get(t[0], 1))
                for t in top20
            ],
        }
        self.results["skill_hot"] = result
        self._save_json("skill_hot.json", result)

        # 横向柱状图
        self._plot_hbar(
            labels=result["skills"][::-1],  # 反转，长的在上面
            values=result["counts"][::-1],
            title="技能热度 Top20",
            filename="skill_top20_bar.png",
        )
        logger.info(f"   Top5 技能: {', '.join(result['skills'][:5])}")
        return result

    # ================================================================
    # 5. 行业薪资对比
    # ================================================================

    def _industry_salary(self):
        """各行业岗位数量和平均薪资（Top15）"""
        logger.info("🏭 分析: 行业薪资对比")

        industry_stats = self.df.groupby("industry").agg(
            count=("salary_avg", "count"),
            avg_salary=("salary_avg", "mean"),
        ).round(0).sort_values("avg_salary", ascending=False)

        top15 = industry_stats.head(15)

        result = {
            "industries": top15.index.tolist(),
            "counts": top15["count"].astype(int).tolist(),
            "avg_salaries": top15["avg_salary"].tolist(),
        }
        self.results["salary_by_industry"] = result
        self._save_json("salary_by_industry.json", result)

        return result

    # ================================================================
    # 6. 发布时间趋势
    # ================================================================

    def _publish_trend(self):
        """岗位发布时间趋势（按周/月聚合）"""
        logger.info("📆 分析: 发布时间趋势")

        if "publish_date" not in self.df.columns:
            self.results["publish_trend"] = {"message": "无发布日期数据"}
            return

        # 解析日期
        dates = pd.to_datetime(self.df["publish_date"], errors="coerce")
        dates = dates.dropna()

        if len(dates) == 0:
            self.results["publish_trend"] = {"message": "日期解析失败"}
            return

        # 按周聚合
        weekly = dates.dt.to_period("W").value_counts().sort_index()
        result = {
            "weeks": [str(w) for w in weekly.index],
            "counts": weekly.values.tolist(),
        }
        self.results["publish_trend"] = result
        self._save_json("publish_trend.json", result)

        return result

    # ================================================================
    # 保存工具
    # ================================================================

    def _save_json(self, filename: str, data):
        """保存单个分析结果为JSON"""
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"   已保存: {filepath}")

    def _save_all(self):
        """所有结果合并保存（给Flask一站式读取）"""
        all_path = os.path.join(self.output_dir, "all_analysis.json")
        with open(all_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        logger.info(f"📦 全部分析结果: {all_path}")

    # ================================================================
    # 图表绘制（Matplotlib → PNG）
    # ================================================================

    def _plot_bar(self, labels, values, title, filename):
        """柱状图"""
        fig, ax = plt.subplots(figsize=(12, 6))
        colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(labels)))
        ax.bar(labels, values, color=colors, edgecolor="white", linewidth=0.5)
        ax.set_title(title, fontsize=16, fontweight="bold")
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=10)
        ax.set_ylabel("平均月薪 (元)", fontsize=12)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout()
        filepath = os.path.join(self.chart_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches="tight")
        plt.close()
        logger.debug(f"   📈 图表: {filepath}")

    def _plot_hbar(self, labels, values, title, filename):
        """横向柱状图（适合技能排行等长标签）"""
        fig, ax = plt.subplots(figsize=(10, 8))
        colors = plt.cm.Oranges(np.linspace(0.4, 0.9, len(labels)))
        ax.barh(labels, values, color=colors, edgecolor="white")
        ax.set_title(title, fontsize=16, fontweight="bold")
        ax.set_xlabel("出现次数", fontsize=12)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout()
        filepath = os.path.join(self.chart_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches="tight")
        plt.close()

    def _plot_pie(self, labels, values, title, filename):
        """饼图"""
        fig, ax = plt.subplots(figsize=(8, 8))
        colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
        wedges, texts, autotexts = ax.pie(
            values, labels=None, autopct="%1.1f%%",
            colors=colors, startangle=90, pctdistance=0.85,
        )
        ax.set_title(title, fontsize=16, fontweight="bold")
        ax.legend(wedges, labels, title="学历", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
        plt.tight_layout()
        filepath = os.path.join(self.chart_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches="tight")
        plt.close()

    def _plot_line(self, x, y, title, xlabel, ylabel, filename):
        """折线图"""
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(x, y, marker="o", linewidth=2, markersize=8, color="#2196F3")
        ax.set_title(title, fontsize=16, fontweight="bold")
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", alpha=0.3)
        plt.tight_layout()
        filepath = os.path.join(self.chart_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches="tight")
        plt.close()


# ================================================================
# 模块入口
# ================================================================
if __name__ == "__main__":
    analyzer = StatisticsAnalyzer()
    analyzer.run()
