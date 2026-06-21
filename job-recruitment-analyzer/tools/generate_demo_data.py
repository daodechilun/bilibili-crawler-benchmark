"""
演示数据生成器
=============
当没有爬取真实数据时，生成2000条仿真数据，
让 Flask 可视化大屏能直接启动演示。

用法：
  python output/generate_demo_data.py
"""
import os
import sys
import random
import csv
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

# ============================================================
# 数据池
# ============================================================
CITIES = ["北京","上海","深圳","杭州","广州","成都","武汉","南京","西安","长沙",
          "苏州","郑州","天津","重庆","东莞","厦门","合肥","青岛","大连","济南"]

DISTRICTS = {
    "北京": ["朝阳区","海淀区","西城区","东城区","丰台区","大兴区"],
    "上海": ["浦东新区","徐汇区","静安区","黄浦区","闵行区"],
    "深圳": ["南山区","福田区","宝安区","龙华区","罗湖区"],
    "杭州": ["滨江区","西湖区","余杭区","拱墅区"],
    "广州": ["天河区","海珠区","番禺区","越秀区"],
}

COMPANIES = [
    "字节跳动","阿里巴巴","腾讯","华为","美团","京东","百度","网易",
    "小米","滴滴","快手","拼多多","携程","商汤科技","科大讯飞",
    "旷视科技","依图科技","寒武纪","地平线","第四范式",
    "明略科技","神策数据","星环科技","Kyligence","StreamNative",
    "XX科技有限公司","YY数据服务有限公司","ZZ信息技术有限公司",
]

INDUSTRIES = [
    "互联网/电子商务","计算机软件","IT服务","人工智能",
    "金融/投资/证券","医疗健康","教育/培训","通信/电信",
    "大数据/云计算","在线教育","新零售","企业服务",
]

EDUCATIONS = ["不限","大专","本科","硕士","博士"]
EDU_WEIGHTS = [10, 25, 45, 18, 2]  # 学历分布权重

EXPERIENCES = ["经验不限","1年以下","1-3年","3-5年","5-7年","7-10年","10年以上"]

SKILL_POOL = [
    "Python","SQL","Java","Spark","Hadoop","Hive","Flink","Kafka",
    "TensorFlow","PyTorch","Scikit-learn","Pandas","NumPy","Jupyter",
    "Docker","Kubernetes","Git","Linux","AWS","Azure","阿里云",
    "MongoDB","Redis","Elasticsearch","ClickHouse","PostgreSQL",
    "Tableau","Power BI","Excel","FineReport",
    "Machine Learning","Deep Learning","NLP","CV",
    "数据仓库","ETL","数据建模","数据治理",
    "Go","C++","Scala","R","MATLAB","Shell",
]

COMPANY_SIZES = ["50-150人","150-500人","500-1000人","1000-5000人","5000-10000人","10000人以上"]
SIZE_WEIGHTS = [5, 10, 25, 35, 15, 10]

KEYWORDS = ["数据分析","Python开发","AI算法","大数据开发"]

# 各关键词对应的典型技能
KEYWORD_SKILLS = {
    "数据分析": ["Python","SQL","Excel","Pandas","NumPy","Tableau","Power BI","数据仓库","ETL","Scikit-learn","数据建模"],
    "Python开发": ["Python","Django","Flask","FastAPI","Docker","Git","Linux","MySQL","Redis","MongoDB","Kubernetes","AWS","Go","Shell"],
    "AI算法": ["Python","TensorFlow","PyTorch","Deep Learning","Machine Learning","NLP","CV","Scikit-learn","Keras","CUDA","Linux","Docker"],
    "大数据开发": ["Java","Scala","Spark","Hadoop","Hive","Flink","Kafka","HBase","ClickHouse","Elasticsearch","数据仓库","ETL","Linux","Shell"],
}


def random_date(days_back=90):
    """随机生成过去N天内的日期"""
    delta = timedelta(days=random.randint(0, days_back))
    return (datetime.now() - delta).strftime("%Y-%m-%d")


def random_salary(city, keyword):
    """根据城市和关键词生成合理的薪资"""
    base = {
        "数据分析": (8000, 15000),
        "Python开发": (10000, 18000),
        "AI算法": (15000, 25000),
        "大数据开发": (12000, 20000),
    }
    city_mult = {
        "北京": 1.4, "上海": 1.35, "深圳": 1.3, "杭州": 1.15, "广州": 1.05,
        "成都": 0.85, "武汉": 0.8, "南京": 0.95, "西安": 0.75, "长沙": 0.75,
        "苏州": 0.9, "郑州": 0.7, "天津": 0.8, "重庆": 0.75, "东莞": 0.75,
    }

    lo, hi = base.get(keyword, (8000, 15000))
    mult = city_mult.get(city, 0.8)
    lo = int(lo * mult // 1000 * 1000)
    hi = int(hi * mult // 1000 * 1000)

    if random.random() < 0.15:
        return None  # 15%面议
    min_s = random.randint(lo, hi - 2000)
    max_s = min_s + random.randint(2000, min(20000, hi - min_s))
    return min_s, max_s


def random_skills(keyword, count=None):
    """根据关键词生成相关技能标签"""
    if count is None:
        count = random.randint(2, 8)
    pool = KEYWORD_SKILLS.get(keyword, SKILL_POOL[:15])
    skills = random.sample(pool, min(count, len(pool)))
    # 偶尔加点其他技能
    if random.random() < 0.3:
        extra = random.choice([s for s in SKILL_POOL if s not in skills])
        skills.append(extra)
    return ", ".join(skills)


def generate_records(n=2100):
    """生成N条仿真招聘数据"""
    records = []
    for i in range(n):
        city = random.choice(CITIES)
        keyword = random.choice(KEYWORDS)

        # 薪资
        salary_tuple = random_salary(city, keyword)
        if salary_tuple:
            smin, smax = salary_tuple
            savg = round((smin + smax) / 2)
            salary_text = f"{smin//1000}-{smax//1000}K"
        else:
            smin, smax, savg = None, None, None
            salary_text = "面议"

        education = random.choices(EDUCATIONS, weights=EDU_WEIGHTS, k=1)[0]
        exp_text = random.choice(EXPERIENCES)

        if exp_text == "经验不限":
            emin, emax = 0, 0
        elif "以上" in exp_text:
            emin = float(exp_text.replace("年以上", "").strip())
            emax = 999
        elif "以下" in exp_text:
            emax = float(exp_text.replace("年以下", "").strip())
            emin = 0
        else:
            nums = exp_text.replace("年","").split("-")
            emin = float(nums[0].strip()) if len(nums) >= 1 else 0
            emax = float(nums[1].strip()) if len(nums) >= 2 else emin

        record = {
            "job_title": f"{keyword}{random.choice(['工程师','专家','经理','总监','实习生',''])}",
            "salary_text": salary_text,
            "salary_min": smin if smin else "",
            "salary_max": smax if smax else "",
            "salary_avg": savg if savg else "",
            "city": city,
            "district": random.choice(DISTRICTS.get(city, [""])),
            "city_tier": config.CITY_TIER.get(city, "其他"),
            "education": education,
            "experience": exp_text,
            "exp_min": emin,
            "exp_max": emax,
            "company_name": random.choice(COMPANIES),
            "company_size": random.choices(COMPANY_SIZES, weights=SIZE_WEIGHTS, k=1)[0],
            "industry": random.choice(INDUSTRIES),
            "skill_tags": random_skills(keyword),
            "publish_date": random_date(90),
            "job_url": f"https://jobs.51job.com/all/{10000000+i}.html",
            "keyword": keyword,
        }
        records.append(record)
    return records


def main():
    print("[DEMO] 生成演示数据...")

    records = generate_records(2100)

    # 保存 raw CSV
    raw_path = os.path.join(config.RAW_DIR, "raw_data.csv")
    if records:
        fieldnames = list(records[0].keys())
        with open(raw_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
        print(f"[OK] 原始数据: {raw_path} ({len(records)} 条)")

    # 同时生成 cleaned CSV（跳过清洗流程，直接生成"看起来干净"的数据）
    cleaned_path = os.path.join(config.CLEANED_DIR, "cleaned_data.csv")
    # 过滤无薪资的记录
    cleaned = [r for r in records if r["salary_avg"] != ""]
    if cleaned:
        with open(cleaned_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(cleaned)
        print(f"[OK] 清洗数据: {cleaned_path} ({len(cleaned)} 条)")

    # 生成 JSON
    json_path = os.path.join(config.CLEANED_DIR, "cleaned_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    print(f"[OK] JSON数据: {json_path}")

    print("\n[DATA] 数据统计:")
    print(f"   总记录: {len(records)}")
    print(f"   有薪资: {len(cleaned)} ({len(cleaned)/len(records)*100:.1f}%)")
    print(f"   城市数: {len(set(r['city'] for r in records))}")
    print(f"   关键词: {', '.join(KEYWORDS)}")
    print("\n现在可以运行: python main.py visualize")


if __name__ == "__main__":
    main()
