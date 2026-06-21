"""
Flask 可视化后端 v3
===================
路由：
  1. GET  /              → 仪表盘HTML页面
  2. GET  /api/dashboard → 基础6张图表数据（支持筛选联动）
  3. GET  /api/kpi       → KPI 数字卡片数据
  4. GET  /api/ml/clusters  → 聚类画像数据
  5. GET  /api/ml/models    → 薪资预测模型对比
  6. GET  /api/ml/features  → 特征重要性
  7. GET  /api/filter_options → 筛选下拉框选项
"""
import os
import sys
import json
import random
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from flask import Flask, render_template, jsonify, request

import config

app = Flask(__name__)

# ================================================================
# 全局数据加载
# ================================================================

def _load_data():
    cleaned_path = os.path.join(config.CLEANED_DIR, "cleaned_data.csv")
    if not os.path.exists(cleaned_path):
        print(f"[WARN] 找不到清洗数据: {cleaned_path}")
        return pd.DataFrame()

    df = pd.read_csv(cleaned_path, encoding="utf-8-sig")
    for col in ["salary_avg", "salary_min", "salary_max", "exp_min", "exp_max"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["province"] = df["city"].map(config.CITY_TO_PROVINCE).fillna(df["city"])
    exp_bins = [0, 1, 3, 5, 7, 10, 100]
    exp_labels = ["0-1年", "1-3年", "3-5年", "5-7年", "7-10年", "10年+"]
    df["exp_bin"] = pd.cut(df["exp_min"], bins=exp_bins, labels=exp_labels, right=False)
    df["skill_count"] = df["skill_tags"].fillna("").apply(
        lambda x: len([t.strip() for t in str(x).split(",") if t.strip()]) if x and str(x) != "nan" else 0
    )
    print(f"[LOAD] 可视化数据: {len(df)} 条")
    return df

DATA = _load_data()

# 预加载 ML 分析结果
def _load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

ML_CLUSTERS = _load_json(os.path.join(config.BASE_DIR, "analysis", "cluster_profile.json"))
ML_MODELS = _load_json(os.path.join(config.BASE_DIR, "analysis", "salary_predict_results.json"))
ML_FEATURES = _load_json(os.path.join(config.BASE_DIR, "analysis", "feature_importance.json"))

# ================================================================
# 路由1: 首页
# ================================================================

@app.route("/")
def index():
    return render_template("index.html")

# ================================================================
# 路由2: KPI 汇总
# ================================================================

@app.route("/api/kpi")
def kpi_api():
    if len(DATA) == 0:
        return jsonify({"error": "无数据"}), 200

    total = len(DATA)
    avg_salary = round(DATA["salary_avg"].mean(), 0)
    top_city = DATA.groupby("city")["salary_avg"].mean().idxmax()
    top_city_salary = round(DATA.groupby("city")["salary_avg"].mean().max(), 0)

    # 获取最热技能
    skill_counter = Counter()
    for tags in DATA["skill_tags"]:
        if pd.isna(tags) or str(tags) == "nan":
            continue
        for tag in str(tags).split(","):
            tag = tag.strip()
            if tag and tag not in _SKILL_BLOCKLIST:
                skill_counter[tag] += 1
    top_skill = skill_counter.most_common(1)[0][0] if skill_counter else "--"

    # 聚类簇数
    n_clusters = ML_CLUSTERS.get("k_selection", {}).get("optimal_k", 9)
    silhouette = ML_CLUSTERS.get("k_selection", {}).get("silhouettes", [0])[-1]
    silhouette = round(silhouette, 3) if silhouette else 0

    # 最优模型
    best_model = ML_MODELS.get("best_model", "LinearRegression")
    best_r2 = 0
    for m in ML_MODELS.get("model_compare", []):
        if m["model"] == best_model:
            best_r2 = round(m["R2"], 3)
            break

    return jsonify({
        "total_jobs": total,
        "avg_salary": int(avg_salary),
        "top_city": top_city,
        "top_city_salary": int(top_city_salary),
        "top_skill": top_skill,
        "n_clusters": n_clusters,
        "silhouette": silhouette,
        "best_model": best_model,
        "best_r2": best_r2,
    })

# ================================================================
# 路由3: 仪表盘图表数据（支持筛选）
# ================================================================

@app.route("/api/dashboard")
def dashboard_api():
    city = request.args.get("city", "").strip()
    education = request.args.get("education", "").strip()
    keyword = request.args.get("keyword", "").strip()
    exp_range = request.args.get("exp_range", "").strip()

    df = DATA.copy()
    if city:
        df = df[df["city"] == city]
    if education:
        df = df[df["education"] == education]
    if keyword:
        df = df[df["keyword"] == keyword]
    if exp_range:
        try:
            parts = exp_range.split("-")
            lo, hi = float(parts[0]), float(parts[1])
            df = df[(df["exp_min"] >= lo) & (df["exp_min"] < hi)]
        except ValueError:
            pass

    if len(df) == 0:
        return jsonify({"error": "筛选后无数据", "count": 0}), 200

    result = {
        "count": int(len(df)),
        "filters": {"city": city, "education": education, "keyword": keyword},
        "chart_bar_city": _chart_bar_city(df),
        "chart_pie_edu": _chart_pie_edu(df),
        "chart_scatter_exp": _chart_scatter_exp(df),
        "chart_map_province": _chart_map_province(df),
        "chart_wordcloud": _chart_wordcloud(df),
        "chart_line_exp": _chart_line_exp(df),
        "chart_industry": _chart_industry(df),
    }
    return jsonify(result)

# ================================================================
# 路由4: ML 聚类数据（静态，不随筛选变化）
# ================================================================

@app.route("/api/ml/clusters")
def ml_clusters():
    profiles = ML_CLUSTERS.get("cluster_profiles", [])
    k_data = ML_CLUSTERS.get("k_selection", {})
    return jsonify({
        "optimal_k": k_data.get("optimal_k", 9),
        "silhouettes": k_data.get("silhouettes", []),
        "inertias": k_data.get("inertias", []),
        "k_values": k_data.get("k_values", []),
        "profiles": [{
            "id": p["cluster_id"],
            "name": p.get("cluster_name", f"簇{p['cluster_id']}"),
            "count": p["count"],
            "pct": p["percentage"],
            "avg_salary": p["avg_salary"],
            "avg_exp": p["avg_experience"],
            "edu": p["education_mode"],
            "top5_skills": p.get("top5_skills", []),
            "top_industries": list(p.get("top3_industries", {}).keys())[:3],
            "top_cities": list(p.get("top3_cities", {}).keys())[:3],
        } for p in profiles],
    })

# ================================================================
# 路由5: ML 模型对比
# ================================================================

@app.route("/api/ml/models")
def ml_models():
    mc = ML_MODELS.get("model_compare", [])
    fi = ML_MODELS.get("feature_importance", {})
    return jsonify({
        "models": [{"name": m["model"], "R2": m["R2"], "RMSE": m["RMSE"], "MAE": m["MAE"]} for m in mc],
        "best": ML_MODELS.get("best_model", ""),
        "feature_importance": fi,
    })

# ================================================================
# 路由6: 特征重要性
# ================================================================

@app.route("/api/ml/features")
def ml_features():
    return jsonify(ML_FEATURES)

# ================================================================
# 路由7: 筛选选项
# ================================================================

@app.route("/api/filter_options")
def filter_options():
    if len(DATA) == 0:
        return jsonify({})
    return jsonify({
        "cities": sorted(DATA["city"].dropna().unique().tolist()),
        "educations": sorted(DATA["education"].dropna().unique().tolist()),
        "keywords": sorted(DATA["keyword"].dropna().unique().tolist()),
        "exp_ranges": ["0-1年", "1-3年", "3-5年", "5-7年", "7-10年"],
    })

# ================================================================
# 图表计算函数
# ================================================================

def _chart_bar_city(df):
    stats = df.groupby("city").agg(avg_salary=("salary_avg", "mean"), count=("salary_avg", "count")).round(0).sort_values("avg_salary", ascending=False).head(12)
    return {"x": stats.index.tolist(), "avg_salaries": stats["avg_salary"].tolist(), "counts": stats["count"].astype(int).tolist()}

def _chart_pie_edu(df):
    edu = df["education"].value_counts()
    # 附加均薪
    edu_salary = df.groupby("education")["salary_avg"].mean().round(0)
    return {"data": [{"name": k, "value": int(v), "avg_salary": int(edu_salary.get(k, 0))} for k, v in edu.items()]}

def _chart_scatter_exp(df):
    top_cities = df["city"].value_counts().head(10).index.tolist()
    series = []
    city_idx = {c: i for i, c in enumerate(top_cities)}
    for c in top_cities:
        subset = df[df["city"] == c]
        data = []
        for s in subset["salary_avg"]:
            if pd.isna(s): continue
            data.append([round(city_idx[c] + random.uniform(-0.4, 0.4), 2), round(s, 0)])
        series.append({"name": c, "data": data})
    return {"categories": top_cities, "series": series}

CITY_TO_GEOJSON = {
    "广州": "广州市", "深圳": "深圳市", "珠海": "珠海市", "肇庆": "肇庆市",
    "东莞": "东莞市", "佛山": "佛山市", "中山": "中山市", "惠州": "惠州市",
    "江门": "江门市", "汕头": "汕头市", "湛江": "湛江市", "茂名": "茂名市",
}

def _chart_map_province(df):
    city_counts = df.groupby("city").size().reset_index(name="value")
    data = [{"name": CITY_TO_GEOJSON.get(row["city"], row["city"]), "value": int(row["value"])} for _, row in city_counts.iterrows()]
    return {"data": data}

_SKILL_BLOCKLIST = {
    "本科", "大专", "硕士", "博士", "不限", "中技", "中专", "高中", "初中及以下",
    "无需经验", "1年", "1年及以上", "2年及以上", "3年及以上", "5年及以上",
    "8年及以上", "1-3年", "2-3年", "2-5年", "3-5年", "3-4年", "5-7年", "5-10年",
    "五险一金", "六险一金", "五险", "补充医疗保险", "补充公积金", "商业保险",
    "带薪年假", "带薪病假", "年终奖金", "绩效奖金", "项目奖金", "股票期权",
    "定期体检", "定期团建", "专业培训", "培训", "餐饮补贴", "餐补", "有餐补",
    "节日福利", "员工旅游", "通讯补贴", "交通补贴", "出差补贴", "住房补贴",
    "弹性工作", "周末双休", "双休", "出国机会", "免费班车", "免费停车",
    "零食下午茶", "下午茶", "节假日", "全勤奖", "工龄奖", "管理规范",
    "计算机", "计算机科学", "编程语言", "编程", "软件工程", "软件开发",
    "后端开发", "需求分析", "自动化",
}

def _chart_wordcloud(df):
    skill_counter = Counter()
    for tags in df["skill_tags"]:
        if pd.isna(tags) or str(tags) == "nan": continue
        for tag in str(tags).split(","):
            tag = tag.strip()
            if tag and tag not in _SKILL_BLOCKLIST:
                skill_counter[tag] += 1
    top50 = skill_counter.most_common(50)
    return {"data": [{"name": n, "value": v} for n, v in top50]}

def _chart_line_exp(df):
    exp_stats = df.groupby("exp_bin", observed=False).agg(avg_salary=("salary_avg", "mean"), count=("salary_avg", "count")).round(0).dropna()
    x_labels = exp_stats.index.tolist()
    series = [{"name": "全部", "avg_salaries": exp_stats["avg_salary"].tolist(), "counts": exp_stats["count"].astype(int).tolist()}]
    for kw in sorted(df["keyword"].dropna().unique().tolist()):
        kw_df = df[df["keyword"] == kw]
        kw_stats = kw_df.groupby("exp_bin", observed=False).agg(avg_salary=("salary_avg", "mean"), count=("salary_avg", "count")).round(0).dropna()
        salary_list = [kw_stats.loc[label, "avg_salary"] if label in kw_stats.index else None for label in x_labels]
        count_list = [int(kw_stats.loc[label, "count"]) if label in kw_stats.index else 0 for label in x_labels]
        series.append({"name": kw, "avg_salaries": salary_list, "counts": count_list})
    return {"x": x_labels, "series": series}

def _chart_industry(df):
    stats = df.groupby("industry").agg(avg_salary=("salary_avg", "mean"), count=("salary_avg", "count")).round(0).sort_values("avg_salary", ascending=False).head(10)
    return {"industries": stats.index.tolist(), "avg_salaries": stats["avg_salary"].tolist(), "counts": stats["count"].astype(int).tolist()}

# ================================================================
# 启动
# ================================================================

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  [WEB] IT岗位数据分析可视化系统 v3")
    print(f"  访问: http://{config.FLASK_HOST}:{config.FLASK_PORT}")
    print("  ML数据: 聚类 + 薪资预测 + 特征重要性 已接入")
    print("=" * 50 + "\n")
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG)
