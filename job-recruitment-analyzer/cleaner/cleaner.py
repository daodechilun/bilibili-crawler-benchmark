"""
数据清洗主流水线
================
读 raw_data.csv → 逐字段清洗 → 去重 → 导出 → 入库 MySQL

清洗规则一览：
  1. 薪资字段   — 「15-25K·14薪」→ min/max/avg 数值，处理日薪/时薪/年薪
  2. 城市字段   — 统一标准名 + 标注 city_tier（一线/新一线/二线）
  3. 学历字段   — 统一枚举：不限/大专/本科/硕士/博士
  4. 经验字段   — 「3-5年」→ exp_min=3, exp_max=5
  5. 技能标签   — 🔥 从岗位描述中提取（正则+关键词词典）
  6. 异常值     — 删除薪资为0或>100万的记录
  7. 缺失值     — 数值用中位数填，分类用众数填
  8. 去重       — 🔥 company_name + job_title + salary 联合去重

每步都打印进度，方便你知道洗到了哪一步、洗掉多少条数据。
"""
import os
import json
import re
import csv
from typing import Dict, List, Tuple, Optional
from datetime import datetime

import pandas as pd
import numpy as np
from loguru import logger

import config
from parser.salary_parser import (
    parse_salary, normalize_city, normalize_education, parse_experience
)
from cleaner.validator import DataValidator
from storage.csv_handler import read_csv, write_csv
from storage.db_handler import db


# ============================================================
# 🔥 技能关键词词典
# ============================================================
# 常见的IT技能，用于从岗位描述/标签中识别
SKILL_DICT = {
    # 编程语言
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Golang", "Rust",
    "C++", "C", "C#", "Scala", "Kotlin", "Swift", "PHP", "Ruby", "Perl",
    "Shell", "Bash", "MATLAB", "R",
    # 数据库
    "SQL", "MySQL", "PostgreSQL", "Oracle", "MongoDB", "Redis",
    "Elasticsearch", "ClickHouse", "HBase", "Neo4j", "TDengine", "Doris",
    # 大数据
    "Spark", "Hadoop", "Hive", "Flink", "Kafka", "Storm", "Airflow",
    "Zookeeper", "Sqoop", "DataX", "Azkaban", "DolphinScheduler",
    # AI / ML
    "Machine Learning", "深度学习", "自然语言处理", "计算机视觉",
    "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "XGBoost",
    "Pandas", "NumPy", "Scipy", "Jupyter", "MLflow", "Kubeflow",
    # 数据工程
    "ETL", "数据仓库", "数据湖", "数据建模", "数据治理",
    "Tableau", "Power BI", "FineReport", "Metabase", "Superset",
    # 云计算
    "AWS", "Azure", "GCP", "阿里云", "腾讯云", "华为云",
    "Docker", "Kubernetes", "K8s", "Jenkins", "Git", "CI/CD",
    "Linux", "Unix",
    # 其他
    "Excel", "SPSS", "SAS", "VBA", "爬虫", "Scrapy", "Selenium",
    "数据分析", "数据挖掘", "数据可视化",
}

# 技能别名词典（统一为规范写法）
# 🔥 这些同义词如果不归一，做词云和TF-IDF时会被当成不同的词
SKILL_ALIAS = {
    # 编程语言同义词
    "Golang": "Go",
    "Python3": "Python", "python3": "Python", "python": "Python",
    "JS": "JavaScript", "Node.js": "JavaScript", "NodeJS": "JavaScript",
    "TypeScript": "JavaScript",  # 前端聚类时合并
    "CPP": "C++", "C plus plus": "C++",
    # 框架/工具同义词
    "K8s": "Kubernetes", "k8s": "Kubernetes",
    "sklearn": "Scikit-learn", "scikit_learn": "Scikit-learn",
    "tf": "TensorFlow", "TF": "TensorFlow",
    "torch": "PyTorch",
    "xgboost": "XGBoost", "xgb": "XGBoost",
    "sklearn": "Scikit-learn",
    "plt": "Matplotlib", "plotly": "Plotly",
    # AI/ML 中英文同义词
    "深度学习": "Deep Learning", "Deep Learning": "Deep Learning",
    "自然语言处理": "NLP", "NLP": "NLP", "nlp": "NLP",
    "计算机视觉": "CV", "CV": "CV", "cv": "CV",
    "机器学习": "Machine Learning", "machine learning": "Machine Learning", "ML": "Machine Learning",
    # 数据工程同义词
    "爬虫": "Web Scraping", "网络爬虫": "Web Scraping",
    "数据挖掘": "Data Mining", "data mining": "Data Mining",
    "数据可视化": "Data Visualization", "data visualization": "Data Visualization",
    "数仓": "数据仓库", "数据仓库": "数据仓库",
    # 数据库同义词
    "关系型数据库": "SQL", "RDBMS": "SQL",
    "pg": "PostgreSQL",
    "mongo": "MongoDB",
    "es": "Elasticsearch", "ES": "Elasticsearch",
    # 云计算同义词
    "阿里云": "Aliyun", "aliyun": "Aliyun",
    "腾讯云": "Tencent Cloud", "华为云": "Huawei Cloud",
    "docker": "Docker",
    # 其他
    "office": "Excel", "ms office": "Excel",
    "powerbi": "Power BI", "power bi": "Power BI",
    "ci": "CI/CD", "cd": "CI/CD",
    "git": "Git",
    "linux": "Linux",
}

# 编译好的正则（匹配常见技能写法）
SKILL_PATTERN = re.compile(
    r'(Python|Java|SQL|Spark|Hadoop|Hive|Flink|Kafka|Docker|Kubernetes|K8s|'
    r'TensorFlow|PyTorch|Scikit-learn|Pandas|NumPy|Excel|Tableau|Power\s*BI|'
    r'Linux|Git|AWS|Azure|GCP|MongoDB|Redis|Elasticsearch|ClickHouse|Go|'
    r'C\+\+|Rust|Scala|MATLAB|R\b|Shell|PHP|Selenium|Scrapy|Jenkins|'
    r'机器学习|深度学习|自然语言处理|计算机视觉|数据分析|数据挖掘)',
    re.IGNORECASE
)


class DataCleaner:
    """
    数据清洗器
    ---------
    封装完整清洗流程：加载 → 校验 → 清洗 → 去重 → 导出 → 入库

    用法：
        cleaner = DataCleaner()
        cleaner.run()
    """

    def __init__(self):
        self.raw_path = os.path.join(config.RAW_DIR, "raw_data.csv")
        self.cleaned_csv = os.path.join(config.CLEANED_DIR, "cleaned_data.csv")
        self.cleaned_json = os.path.join(config.CLEANED_DIR, "cleaned_data.json")
        self.df = None          # pandas DataFrame
        self.raw_count = 0      # 原始条数
        self.cleaned_count = 0  # 清洗后条数
        self.stats = {}         # 统计信息（供报告使用）

    # ================================================================
    # 主入口
    # ================================================================

    def run(self):
        """一键运行完整清洗流程"""
        logger.info("=" * 60)
        logger.info("🧹 数据清洗流水线启动")
        logger.info("=" * 60)

        # Step 1: 加载
        self._load()

        # Step 2: 校验
        self._validate()

        # Step 3: 逐字段清洗
        self._clean_salary()
        self._clean_city()
        self._clean_education()
        self._clean_experience()
        self._clean_skill_tags()
        self._clean_company()

        # Step 4: 去重
        self._deduplicate()

        # Step 5: 缺失值处理
        self._fill_missing()

        # Step 6: 异常值过滤
        self._remove_outliers()

        # Step 7: 导出
        self._export_csv()
        self._export_json()

        # Step 8: 入库 MySQL
        self._to_mysql()

        # 汇总
        self._summary()
        return self.df

    # ================================================================
    # Step 1: 加载数据
    # ================================================================

    def _load(self):
        """读取原始CSV，转为 pandas DataFrame"""
        if not os.path.exists(self.raw_path):
            raise FileNotFoundError(
                f"找不到原始数据文件：{self.raw_path}\n"
                f"请先运行 'python main.py crawl' 采集数据！"
            )

        logger.info(f"📂 加载原始数据: {self.raw_path}")

        # 用 pandas 读取（比 csv 模块快，且有自动类型推断）
        self.df = pd.read_csv(self.raw_path, encoding="utf-8-sig", low_memory=False)
        self.raw_count = len(self.df)
        logger.info(f"   共加载 {self.raw_count} 条原始记录")

        # 把薪资字段从字符串转数值
        for col in ["salary_min", "salary_max", "salary_avg"]:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors="coerce")

    # ================================================================
    # Step 2: 数据校验
    # ================================================================

    def _validate(self):
        """校验数据质量，打印问题统计"""
        validator = DataValidator()
        records = self.df.to_dict("records")
        _, issue_stats = validator.validate_batch(records)

        logger.info(f"🔍 数据校验完成:")
        logger.info(f"   干净记录: {issue_stats['clean']}")
        logger.info(f"   问题记录: {issue_stats['issues']}")
        if issue_stats["issue_breakdown"]:
            logger.info(f"   问题分布:")
            for issue, count in sorted(issue_stats["issue_breakdown"].items(), key=lambda x: -x[1]):
                logger.info(f"     - {issue}: {count} 条")

        self.stats["validation"] = issue_stats

    # ================================================================
    # Step 3a: 薪资清洗
    # ================================================================

    def _clean_salary(self):
        """
        清洗薪资字段

        处理内容：
        1. 对 salary_text 有值但 min/max 为空的行，重新解析
        2. 标记异常薪资（月薪 < 1000 或 > 100000 的不太合理）
        3. 如果 min > max，交换
        """
        logger.info("💵 清洗薪资字段...")

        # 对没有解析出 min/max 但有 salary_text 的行，重新解析
        mask_empty = (
            (self.df["salary_min"].isna() | (self.df["salary_min"] == 0)) &
            self.df["salary_text"].notna() &
            (self.df["salary_text"] != "") &
            (self.df["salary_text"] != "面议")
        )

        reparse_count = 0
        for idx in self.df[mask_empty].index:
            text = self.df.at[idx, "salary_text"]
            smin, smax, savg = parse_salary(str(text))
            if smin is not None:
                self.df.at[idx, "salary_min"] = smin
                self.df.at[idx, "salary_max"] = smax
                self.df.at[idx, "salary_avg"] = savg
                reparse_count += 1

        logger.info(f"   重新解析薪资: {reparse_count} 条")

        # 交换 min > max 的情况
        swap_mask = (
            self.df["salary_min"].notna() &
            self.df["salary_max"].notna() &
            (self.df["salary_min"] > self.df["salary_max"])
        )
        swap_count = swap_mask.sum()
        if swap_count > 0:
            # 交换 min 和 max
            temp = self.df.loc[swap_mask, "salary_min"].copy()
            self.df.loc[swap_mask, "salary_min"] = self.df.loc[swap_mask, "salary_max"]
            self.df.loc[swap_mask, "salary_max"] = temp
            logger.info(f"   修正薪资min>max反转: {swap_count} 条")

        # 已解析出数值的薪资条数统计
        has_salary = self.df["salary_avg"].notna().sum()
        face_to_face = (self.df["salary_text"] == "面议").sum() if "salary_text" in self.df.columns else 0
        logger.info(f"   有明确薪资: {has_salary} 条 | 面议: {face_to_face} 条")

    # ================================================================
    # Step 3b: 城市清洗
    # ================================================================

    def _clean_city(self):
        """标准化城市名 + 标注城市等级"""
        logger.info("🏙️  清洗城市字段...")

        # 对每个城市名用 salary_parser 的 normalize_city 标准化
        city_fix_count = 0
        for idx in self.df.index:
            raw_city = str(self.df.at[idx, "city"]) if pd.notna(self.df.at[idx, "city"]) else ""
            if raw_city and raw_city != "nan":
                std_city, district = normalize_city(raw_city)
                if std_city != raw_city:
                    self.df.at[idx, "city"] = std_city
                    city_fix_count += 1
                # 补充区信息
                if district:
                    self.df.at[idx, "district"] = district

        logger.info(f"   标准化城市名: {city_fix_count} 条")

        # 添加 city_tier 字段
        if "city_tier" not in self.df.columns or self.df["city_tier"].isna().all():
            self.df["city_tier"] = self.df["city"].map(config.CITY_TIER).fillna("其他")

        tier_counts = self.df["city_tier"].value_counts().to_dict()
        logger.info(f"   城市等级分布: {tier_counts}")

    # ================================================================
    # Step 3c: 学历清洗
    # ================================================================

    def _clean_education(self):
        """统一学历为枚举值"""
        logger.info("🎓 清洗学历字段...")

        edu_fix_count = 0
        for idx in self.df.index:
            raw_edu = str(self.df.at[idx, "education"]) if pd.notna(self.df.at[idx, "education"]) else ""
            if raw_edu and raw_edu != "nan":
                std_edu = normalize_education(raw_edu)
                if std_edu != raw_edu:
                    self.df.at[idx, "education"] = std_edu
                    edu_fix_count += 1
            else:
                self.df.at[idx, "education"] = "不限"

        logger.info(f"   统一学历枚举: {edu_fix_count} 条")
        logger.info(f"   学历分布: {self.df['education'].value_counts().to_dict()}")

    # ================================================================
    # Step 3d: 经验清洗
    # ================================================================

    def _clean_experience(self):
        """解析经验字段，拆分为 exp_min / exp_max 数值"""
        logger.info("📅 清洗经验字段...")

        exp_fix_count = 0
        for idx in self.df.index:
            raw_exp = str(self.df.at[idx, "experience"]) if pd.notna(self.df.at[idx, "experience"]) else ""
            exp_min_val = self.df.at[idx, "exp_min"]
            exp_max_val = self.df.at[idx, "exp_max"]

            # 如果 exp_min/max 已经有效值，跳过
            if pd.notna(exp_min_val) and pd.notna(exp_max_val) and (exp_min_val > 0 or raw_exp == "经验不限"):
                continue

            if raw_exp and raw_exp != "nan":
                emin, emax = parse_experience(raw_exp)
                self.df.at[idx, "exp_min"] = emin
                self.df.at[idx, "exp_max"] = emax
                exp_fix_count += 1
            else:
                self.df.at[idx, "exp_min"] = 0.0
                self.df.at[idx, "exp_max"] = 0.0

        # 把 "X年以上" 的 999 标记转换为 exp_min（表示至少 X 年）
        if "exp_max" in self.df.columns:
            over_limit = self.df["exp_max"] > 30
            self.df.loc[over_limit, "exp_max"] = self.df.loc[over_limit, "exp_min"]

        logger.info(f"   解析经验: {exp_fix_count} 条")
        if "exp_min" in self.df.columns:
            logger.info(f"   平均经验要求: {self.df['exp_min'].mean():.1f} ~ {self.df['exp_max'].mean():.1f} 年")

    # ================================================================
    # Step 3e: 🔥 技能标签提取
    # ================================================================

    def _clean_skill_tags(self):
        """
        提取并规范化技能标签

        三步走：
        1. 如果 spider 已经抓到了 skill_tags ← 直接用
        2. 如果 skill_tags 为空 ← 用正则从经验/描述字段中提取
        3. 统一规范写法（如 K8s → Kubernetes）
        """
        logger.info("🏷️  清洗技能标签...")

        extract_count = 0
        enrich_count = 0

        for idx in self.df.index:
            tags = str(self.df.at[idx, "skill_tags"]) if pd.notna(self.df.at[idx, "skill_tags"]) else ""
            tags = tags if tags and tags != "nan" and tags != "无" else ""

            if not tags:
                # 尝试从其他字段提取技能
                extracted = self._extract_skills(idx)
                if extracted:
                    tags = extracted
                    extract_count += 1

            # 规范标签写法
            if tags:
                tags = self._normalize_skill_names(tags)
                # 去重 + 排序
                tag_list = sorted(set(t.strip() for t in tags.split(",") if t.strip()))
                self.df.at[idx, "skill_tags"] = ", ".join(tag_list)
                enrich_count += 1

        logger.info(f"   从描述中提取技能: {extract_count} 条")
        logger.info(f"   有技能标签的岗位: {enrich_count} 条")

    def _extract_skills(self, idx: int) -> str:
        """
        从岗位描述等其他文本中提取技能关键词

        策略：遍历 SKILL_DICT 中的关键词，
              如果在岗位名、行业等字段中出现，就标记为技能。
              注意区分「岗位名本身包含技能词」的情况（如"Python开发"→技能必有Python）。
        """
        found_skills = set()

        # 需要搜索的文本来源
        search_fields = [
            str(self.df.at[idx, "job_title"]) if pd.notna(self.df.at[idx, "job_title"]) else "",
            str(self.df.at[idx, "industry"]) if pd.notna(self.df.at[idx, "industry"]) else "",
            str(self.df.at[idx, "keyword"]) if pd.notna(self.df.at[idx, "keyword"]) else "",
        ]
        search_text = " ".join(search_fields)

        # 用正则匹配已知技能
        matches = SKILL_PATTERN.findall(search_text)
        for m in matches:
            if isinstance(m, tuple):
                # 有些正则分组返回元组，取第一个非空
                m = next((x for x in m if x), "")
            found_skills.add(m.strip())

        # 用关键词词典补充匹配
        search_lower = search_text.lower()
        for skill in SKILL_DICT:
            if skill.lower() in search_lower and len(skill) > 1:
                found_skills.add(skill)

        # 🔥 根据关键词自动补充核心技能（提高准确性）
        keyword = str(self.df.at[idx, "keyword"]) if pd.notna(self.df.at[idx, "keyword"]) else ""
        if "Python" in keyword:
            found_skills.add("Python")
        if "AI" in keyword or "算法" in keyword:
            found_skills.update(["Python", "Machine Learning", "TensorFlow"])
        if "数据分析" in keyword:
            found_skills.update(["Python", "SQL", "Excel", "Pandas"])
        if "大数据" in keyword:
            found_skills.update(["Hadoop", "Spark", "SQL", "Hive"])

        return ", ".join(found_skills) if found_skills else ""

    def _normalize_skill_names(self, tags: str) -> str:
        """统一技能别名（K8s→Kubernetes, 深度学习→Deep Learning）"""
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        normalized = []
        for tag in tag_list:
            normalized.append(SKILL_ALIAS.get(tag, tag))
        return ", ".join(normalized)

    # ================================================================
    # Step 3f: 公司信息清洗
    # ================================================================

    def _clean_company(self):
        """清洗公司名和行业字段"""
        logger.info("🏢 清洗公司信息...")

        # 去除公司名的多余空白和特殊字符
        if "company_name" in self.df.columns:
            self.df["company_name"] = self.df["company_name"].fillna("未知").str.strip()

        # 行业标准化（去除尾部空格和特殊符号）
        if "industry" in self.df.columns:
            self.df["industry"] = self.df["industry"].fillna("未知").str.strip()

        logger.info(f"   公司数: {self.df['company_name'].nunique()}")
        logger.info(f"   行业数: {self.df['industry'].nunique()}")

    # ================================================================
    # Step 4: 🔥 去重
    # ================================================================

    def _deduplicate(self):
        """
        按 company_name + job_title + salary_avg 联合去重

        为什么要这些字段联合去重：
        - 同一家公司可能用不同URL发布相同岗位（内容一样）
        - 只按URL去重不够，因为51job的URL可能有变体
        - 加上薪资作为第三维，避免把「同一公司不同薪资的同名岗」误删
        """
        before = len(self.df)
        logger.info(f"🔍 去重前: {before} 条")

        # 构造联合去重键
        self.df["_dedup_key"] = (
            self.df["company_name"].fillna("").str.strip() + "|||" +
            self.df["job_title"].fillna("").str.strip() + "|||" +
            self.df["salary_avg"].fillna(-1).astype(str)
        )

        # 保留第一条
        self.df = self.df.drop_duplicates(subset=["_dedup_key"], keep="first")
        self.df = self.df.drop(columns=["_dedup_key"])

        after = len(self.df)
        removed = before - after
        logger.info(f"   去重后: {after} 条（删除 {removed} 条重复）")
        self.stats["dedup_removed"] = removed

    # ================================================================
    # Step 5: 缺失值处理
    # ================================================================

    def _fill_missing(self):
        """
        填充缺失值

        规则：
        - 数值型（薪资、经验）→ 用该城市的中位数填充
        - 分类型（学历、公司规模）→ 用该字段的众数填充
        - 面议薪资 → 用同城市同岗位平均薪资填充（🔥 Bo哥要求）
        """
        logger.info("📝 处理缺失值...")

        # --- 薪资缺失填充 ---
        # 优先用同城市平均薪资，次之用全局中位数
        # 🔥 面议占比 > 30% 的城市，填补时乘 1.1 系数（面议岗薪资通常偏高）
        face_ratios = self.stats.get("face_to_face_ratios", {})
        from cleaner.validator import DataValidator
        validator = DataValidator()
        face_ratios = validator.check_face_to_face_ratio(self.df.to_dict("records"))
        self.stats["face_to_face_ratios"] = face_ratios

        for col in ["salary_min", "salary_max", "salary_avg"]:
            if col not in self.df.columns:
                continue
            missing_before = self.df[col].isna().sum()

            # 按城市分组填补
            city_medians = self.df.groupby("city")[col].transform("median")
            self.df[col] = self.df[col].fillna(city_medians)

            # 🔥 面议占比>30%的城市，在填补基础上乘1.1
            for city, ratio in face_ratios.items():
                if ratio > 0.3:
                    mask = (
                        (self.df["city"] == city) &
                        (self.df["salary_text"].str.contains("面议", na=False))
                    )
                    self.df.loc[mask, col] = self.df.loc[mask, col] * 1.1

            # 城市补不了的用全局中位数兜底
            global_median = self.df[col].median()
            self.df[col] = self.df[col].fillna(global_median)

            logger.info(f"   {col}: 填补 {missing_before} 个缺失值")

        # --- 学历缺失填充 ---
        if "education" in self.df.columns:
            edu_mode = self.df["education"].mode()
            if len(edu_mode) > 0:
                self.df["education"] = self.df["education"].fillna(edu_mode[0])

        # --- 经验缺失填充 ---
        for col in ["exp_min", "exp_max"]:
            if col in self.df.columns:
                self.df[col] = self.df[col].fillna(0.0)

        # --- 城市缺失 ---
        if "city" in self.df.columns:
            self.df["city"] = self.df["city"].fillna("未知")

        missing_after = self.df.isna().sum().sum()
        logger.info(f"   剩余缺失值总数: {missing_after}")

    # ================================================================
    # Step 6: 异常值过滤
    # ================================================================

    def _remove_outliers(self):
        """
        删除明显的异常数据

        过滤条件：
        - 薪资 < 0 或 > 1000000
        - 岗位名为空
        """
        before = len(self.df)

        # 删除薪资为负或极端异常的记录
        if "salary_avg" in self.df.columns:
            self.df = self.df[
                (self.df["salary_avg"].isna()) |
                ((self.df["salary_avg"] >= 0) & (self.df["salary_avg"] <= 1000000))
            ]

        # 删除岗位名为空的记录
        if "job_title" in self.df.columns:
            self.df = self.df[self.df["job_title"].notna() & (self.df["job_title"] != "")]

        after = len(self.df)
        logger.info(f"🗑️  异常值过滤: {before} → {after} 条（删除 {before - after} 条）")
        self.stats["outliers_removed"] = before - after

    # ================================================================
    # Step 7: 导出
    # ================================================================

    def _export_csv(self):
        """导出清洗后的CSV"""
        os.makedirs(config.CLEANED_DIR, exist_ok=True)
        self.df.to_csv(self.cleaned_csv, index=False, encoding="utf-8-sig")
        self.cleaned_count = len(self.df)
        logger.info(f"💾 CSV 已保存: {self.cleaned_csv}（{self.cleaned_count} 条）")

    def _export_json(self):
        """导出JSON给Flask使用"""
        # 把 NaN 替换为 null（JSON标准）
        df_json = self.df.where(pd.notna(self.df), None)

        # 选取关键字段导出（减少文件大小）
        export_cols = [
            "job_title", "salary_min", "salary_max", "salary_avg",
            "city", "city_tier", "education",
            "exp_min", "exp_max", "company_name", "company_size",
            "industry", "skill_tags", "publish_date", "keyword",
        ]
        export_cols = [c for c in export_cols if c in df_json.columns]

        records = df_json[export_cols].to_dict(orient="records")

        with open(self.cleaned_json, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        logger.info(f"💾 JSON 已保存: {self.cleaned_json}")

    # ================================================================
    # Step 8: 入库 MySQL
    # ================================================================

    def _to_mysql(self):
        """
        将清洗后的数据批量导入 MySQL

        🔥 每次100条批量提交，不使用一次性全部插入，
        避免 MySQL 报 "Packet too large" 或超时。
        """
        logger.info("🗄️  导入 MySQL...")

        try:
            # 初始化数据库（如果表不存在会自动建）
            db.init_database()

            # 转为字典列表
            records = self.df.where(pd.notna(self.df), None).to_dict(orient="records")

            # 🔥 批量插入，每100条一批
            inserted = db.insert_many(records, batch_size=100)

            self.stats["mysql_inserted"] = inserted
            logger.info(f"✅ MySQL 入库完成: {inserted} 条")
        except Exception as e:
            logger.error(f"❌ MySQL 入库失败: {e}")
            logger.warning("⚠️ 数据已保存为 CSV 和 JSON，MySQL 可稍后手动导入")

    # ================================================================
    # 汇总
    # ================================================================

    def _summary(self):
        """打印清洗结果汇总"""
        logger.info("\n" + "=" * 60)
        logger.info("📊 数据清洗完成汇总")
        logger.info(f"   原始数据: {self.raw_count} 条")
        logger.info(f"   清洗后:   {len(self.df)} 条")
        logger.info(f"   删除重复: {self.stats.get('dedup_removed', 0)} 条")
        logger.info(f"   删除异常: {self.stats.get('outliers_removed', 0)} 条")
        logger.info(f"   数据保留率: {len(self.df)/self.raw_count*100:.1f}%")
        logger.info(f"   输出文件:")
        logger.info(f"     CSV:  {self.cleaned_csv}")
        logger.info(f"     JSON: {self.cleaned_json}")
        logger.info("=" * 60)


# ================================================================
# 模块入口
# ================================================================
if __name__ == "__main__":
    cleaner = DataCleaner()
    cleaner.run()
