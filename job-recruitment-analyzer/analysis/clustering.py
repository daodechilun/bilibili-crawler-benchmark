"""
KMeans 岗位聚类分析
==================
把几千条IT岗位自动分成4~5个簇，然后给每个簇赋予业务含义。

技术路线：
  1. 数值特征：salary_avg + exp_avg + education_encode → StandardScaler
  2. 文本特征：skill_tags → TF-IDF向量 → TruncatedSVD降维到8维
  3. 拼接特征 → KMeans (K=4~5)
  4. 肘部法则 + 轮廓系数确定最优K
  5. 分析每个簇的画像 → 命名（如"高薪AI岗"、"入门数据岗"）

为什么要降维？
  技能TF-IDF是稀疏高维矩阵（几百维），直接丢KMeans会"维度灾难"——
  技能维度之间的欧氏距离远大于薪资/经验的距离，后者会被淹没。
  用TruncatedSVD降到8维，既保留了技能相似性，又让薪资和经验说话。

输出：
  - cluster_profile.json → 每个簇的画像数据
  - cluster_labels.csv → 每条记录的簇标签（可追加到原始数据）
  - elbow_silhouette.png → K值选择图
"""
import os
import json
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from loguru import logger

from sklearn.preprocessing import StandardScaler, OrdinalEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config

plt.rcParams["font.sans-serif"] = ["SimHei", "PingFang SC", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

# 学历有序编码
EDUCATION_ORDER = {"不限": 0, "大专": 1, "本科": 2, "硕士": 3, "博士": 4}


class JobClusterer:
    """
    岗位聚类器
    ----------
    流程：加载→特征工程→K值选择→聚类→画像分析→保存

    用法：
        clusterer = JobClusterer()
        clusterer.run()
    """

    def __init__(self):
        self.cleaned_path = os.path.join(config.CLEANED_DIR, "cleaned_data.csv")
        self.output_dir = os.path.dirname(os.path.abspath(__file__))
        self.chart_dir = os.path.join(config.CHART_DIR)
        self.df = None
        self.X_combined = None       # 拼接后的特征矩阵
        self.labels = None           # 聚类结果
        self.kmeans = None           # 训练好的模型
        self.svd_dim = 5             # 🔥 降到5维（技能5 + 数值3 = 5:3，特征权重均衡）
        self.optimal_k = 4           # 最优簇数
        self.results = {}

    def run(self):
        """一键运行聚类全流程"""
        logger.info("=" * 60)
        logger.info("🔮 KMeans 岗位聚类启动")
        logger.info("=" * 60)

        self._load()
        self._feature_engineering()
        self._find_optimal_k()
        self._cluster()
        self._profile_analysis()
        self._save_results()

        logger.info("✅ 岗位聚类完成")
        return self.results

    # ================================================================
    # 加载数据
    # ================================================================

    def _load(self):
        """加载清洗数据"""
        self.df = pd.read_csv(self.cleaned_path, encoding="utf-8-sig")
        for col in ["salary_avg", "exp_min", "exp_max"]:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors="coerce")

        # 只保留有薪资的样本（聚类需要）
        self.df = self.df[self.df["salary_avg"].notna() & (self.df["salary_avg"] > 0)].copy()
        logger.info(f"📂 加载数据: {len(self.df)} 条（有薪资的有效样本）")

    # ================================================================
    # 特征工程
    # ================================================================

    def _feature_engineering(self):
        """
        构建聚类特征矩阵

        特征分为两部分：
        A. 数值特征（3维）：salary_avg, exp_avg, education_encode
        B. 文本特征（→ TF-IDF → SVD到8维）：skill_tags

        最终拼接为 3 + 8 = 11 维特征矩阵。
        """
        logger.info("🔧 特征工程...")
        df = self.df.copy()

        # ---- Part A: 数值特征 ----
        # 1. 薪资（标准化在最后统一做）
        num_features = pd.DataFrame(index=df.index)
        num_features["salary_avg"] = df["salary_avg"].fillna(df["salary_avg"].median())

        # 2. 经验均值
        num_features["exp_avg"] = df[["exp_min", "exp_max"]].mean(axis=1).fillna(0)

        # 3. 学历有序编码
        num_features["education_enc"] = df["education"].fillna("不限").map(
            EDUCATION_ORDER
        ).fillna(0)

        # ---- Part B: 技能文本特征 ----
        # 构建技能文本（空格分隔，TF-IDF处理）
        df["skill_text"] = df["skill_tags"].fillna("").apply(
            lambda x: " ".join([t.strip() for t in str(x).split(",") if t.strip()])
            if x and str(x) != "nan" else "无"
        )

        # TF-IDF向量化
        tfidf = TfidfVectorizer(
            max_features=config.TFIDF_MAX_FEATURES,
            min_df=2,           # 至少出现在2个岗位中
            max_df=0.8,         # 出现在80%以上岗位中的词视为噪声
            ngram_range=(1, 2), # 单个词 + 双词组合
            sublinear_tf=True,  # 对词频取对数（1+log(tf)）
        )
        tfidf_matrix = tfidf.fit_transform(df["skill_text"])
        logger.info(f"   TF-IDF矩阵: {tfidf_matrix.shape[0]}条 × {tfidf_matrix.shape[1]}个特征词")

        # 🔥 TruncatedSVD降维（适合稀疏矩阵，比PCA快得多）
        svd = TruncatedSVD(n_components=self.svd_dim, random_state=42)
        skill_svd = svd.fit_transform(tfidf_matrix)
        explained = svd.explained_variance_ratio_.sum()
        logger.info(f"   SVD降维: {tfidf_matrix.shape[1]} → {self.svd_dim} 维")
        logger.info(f"   🔍 SVD信息保留率: {explained:.2%}（真实数据中Python+PyTorch共现，预计30-50%）")
        if explained < 0.2:
            logger.warning(f"   ⚠️ 保留率偏低，建议在config.py中调高svd_dim到8-10维")

        # SVD各维度命名（方便后续解释）
        svd_cols = [f"skill_dim{i+1}" for i in range(self.svd_dim)]
        skill_df = pd.DataFrame(skill_svd, index=df.index, columns=svd_cols)

        # 🔥 拼接：技能5维 + 数值3维 = 5:3（特征权重均衡，技能不会淹没薪资经验）
        X_raw = np.hstack([num_features.values, skill_df.values])

        # 🔥 StandardScaler：统一量纲（薪资几万 vs 经验个位数）
        self.scaler = StandardScaler()
        self.X_combined = self.scaler.fit_transform(X_raw)

        self.feature_names = list(num_features.columns) + svd_cols
        logger.info(f"   最终特征矩阵: {self.X_combined.shape}")

    # ================================================================
    # K值选择（肘部法则 + 轮廓系数）
    # ================================================================

    def _find_optimal_k(self):
        """
        用肘部法则和轮廓系数确定最优K值

        肘部法则：惯性下降曲线出现"拐点"的K值
        轮廓系数：越接近1说明簇内紧密、簇间分离越好
        """
        logger.info("📐 K值选择（肘部法则 + 轮廓系数）...")

        k_range = config.KMEANS_K_RANGE
        inertias = []
        silhouettes = []

        for k in k_range:
            km = KMeans(n_clusters=k, random_state=42, n_init=10, max_iter=300)
            labels = km.fit_predict(self.X_combined)
            inertias.append(km.inertia_)
            if k >= 2:
                sil = silhouette_score(self.X_combined, labels)
                silhouettes.append(sil)
                logger.debug(f"   K={k}: 惯性={km.inertia_:.0f}, 轮廓系数={sil:.4f}")
            else:
                silhouettes.append(0)

        # 选择轮廓系数最大的K（≥3）
        best_k_idx = np.argmax(silhouettes[1:]) + 1  # 跳过K=2
        self.optimal_k = list(k_range)[best_k_idx + 1]  # +1因为silhouettes从K=2开始

        # 如果轮廓系数都不理想，用最大K-1
        if max(silhouettes) < 0.2:
            self.optimal_k = 4  # 兜底

        logger.info(f"   🏆 最优K = {self.optimal_k}（轮廓系数={max(silhouettes):.4f}）")

        self.results["k_selection"] = {
            "k_values": list(k_range),
            "inertias": inertias,
            "silhouettes": silhouettes,
            "optimal_k": self.optimal_k,
        }

        # 画K值选择图
        self._plot_k_selection(list(k_range), inertias, silhouettes)

    def _plot_k_selection(self, k_values, inertias, silhouettes):
        """画肘部法则+轮廓系数双图"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        # 肘部法则
        ax1.plot(k_values, inertias, "o-", color="#2196F3", linewidth=2, markersize=8)
        ax1.axvline(x=self.optimal_k, color="red", linestyle="--", label=f"最优K={self.optimal_k}")
        ax1.set_title("肘部法则 (Elbow Method)", fontsize=14, fontweight="bold")
        ax1.set_xlabel("K值", fontsize=12)
        ax1.set_ylabel("惯性 (Inertia)", fontsize=12)
        ax1.legend()
        ax1.spines["top"].set_visible(False)
        ax1.spines["right"].set_visible(False)

        # 轮廓系数
        ax2.plot(k_values[1:], silhouettes[1:], "s-", color="#FF9800", linewidth=2, markersize=8)
        ax2.axvline(x=self.optimal_k, color="red", linestyle="--", label=f"最优K={self.optimal_k}")
        ax2.set_title("轮廓系数 (Silhouette Score)", fontsize=14, fontweight="bold")
        ax2.set_xlabel("K值", fontsize=12)
        ax2.set_ylabel("轮廓系数", fontsize=12)
        ax2.legend()
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)

        plt.tight_layout()
        filepath = os.path.join(self.chart_dir, "elbow_silhouette.png")
        plt.savefig(filepath, dpi=150, bbox_inches="tight")
        plt.close()
        logger.info(f"   📈 K值选择图: {filepath}")

    # ================================================================
    # 聚类
    # ================================================================

    def _cluster(self):
        """执行KMeans聚类"""
        logger.info(f"🔮 执行 KMeans 聚类 (K={self.optimal_k})...")

        self.kmeans = KMeans(
            n_clusters=self.optimal_k,
            random_state=42,
            n_init=10,
            max_iter=300,
        )
        self.labels = self.kmeans.fit_predict(self.X_combined)

        # 各簇样本数
        unique, counts = np.unique(self.labels, return_counts=True)
        for u, c in zip(unique, counts):
            logger.info(f"   簇{u}: {c} 个样本")

        # 追加到DataFrame
        self.df["cluster"] = self.labels

    # ================================================================
    # 🔥 簇画像分析（业务解释——答辩最加分环节）
    # ================================================================

    def _profile_analysis(self):
        """
        分析每个簇的特征，赋予业务含义

        每个簇输出：
        - 样本数、占比
        - 平均薪资、平均经验
        - 学历分布
        - Top5 技能
        - 主要行业
        - 簇命名（如"高薪AI岗"、"入门数据岗"）
        """
        logger.info("\n📋 簇画像分析:")

        profiles = []
        cluster_names = {}  # 自动或手动命名

        for c in range(self.optimal_k):
            subset = self.df[self.df["cluster"] == c]
            n = len(subset)

            # 数值统计
            avg_salary = round(subset["salary_avg"].mean(), 0)
            avg_exp = round(subset[["exp_min", "exp_max"]].mean(axis=1).mean(), 1)
            edu_mode = subset["education"].mode().iloc[0] if len(subset["education"].mode()) > 0 else "未知"

            # Top5技能
            skill_counter = {}
            for tags in subset["skill_tags"]:
                if pd.isna(tags) or str(tags) == "nan":
                    continue
                for tag in str(tags).split(","):
                    tag = tag.strip()
                    if tag:
                        skill_counter[tag] = skill_counter.get(tag, 0) + 1
            top5 = [s[0] for s in sorted(skill_counter.items(), key=lambda x: -x[1])[:5]]

            # Top3行业
            industry_top = subset["industry"].value_counts().head(3).to_dict()

            # Top3城市
            city_top = subset["city"].value_counts().head(3).to_dict()

            profile = {
                "cluster_id": int(c),
                "count": n,
                "percentage": round(n / len(self.df) * 100, 1),
                "avg_salary": avg_salary,
                "avg_experience": avg_exp,
                "education_mode": edu_mode,
                "top5_skills": top5,
                "top3_industries": industry_top,
                "top3_cities": city_top,
            }
            profiles.append(profile)

            # 打印
            logger.info(f"   ┌─ 簇{c}: {n}条 ({n/len(self.df)*100:.1f}%)")
            logger.info(f"   │  平均薪资: {avg_salary:.0f}元/月")
            logger.info(f"   │  平均经验: {avg_exp:.1f}年")
            logger.info(f"   │  主要学历: {edu_mode}")
            logger.info(f"   │  Top5技能: {', '.join(top5)}")
            logger.info(f"   │  主要行业: {list(industry_top.keys())}")
            logger.info(f"   └─ 主要城市: {list(city_top.keys())}")

        # 🔥 自动命名（基于薪资和技能）
        for p in profiles:
            name = self._auto_name(p)
            p["cluster_name"] = name
            logger.info(f"   🏷️  簇{p['cluster_id']}: {name}")

        self.results["cluster_profiles"] = profiles
        self.results["cluster_names"] = {p["cluster_id"]: p["cluster_name"] for p in profiles}

    def _auto_name(self, profile: dict) -> str:
        """
        根据簇特征自动命名（v2：技能词混入福利词不可靠，改用薪资+经验+学历综合判断）

        命名规则（优先级从高到低）：
        - 薪资 > 30k → 高薪资深岗
        - 薪资 > 20k + 学历硕博 → 高学历高薪岗
        - 薪资 > 20k + 行业含AI/算法 → 高薪技术岗
        - 薪资 > 16k → 中高级技术岗
        - 薪资 > 12k + 经验 < 2 → 入门分析岗
        - 薪资 > 8k + 经验 < 1.5 → 初级入门岗
        - 薪资 > 8k → 中级技术岗
        - 其他 → 初级通用岗
        """
        salary = profile["avg_salary"]
        exp = profile["avg_experience"]
        edu = profile.get("education_mode", "本科")
        industries = list(profile.get("top3_industries", {}).keys())

        # 是否为高学历簇
        is_high_edu = edu in ("硕士", "博士")

        # 是否为AI/技术密集型（从行业名判断）
        is_ai_industry = any(
            kw in str(ind) for ind in industries
            for kw in ["人工智能", "AI", "算法", "半导体", "芯片"]
        )

        if salary > 30000:
            return "高薪资深岗" if exp >= 4 else "超高薪技术岗"
        elif salary > 20000 and is_high_edu:
            return "高学历高薪岗"
        elif salary > 20000 and is_ai_industry:
            return "高薪技术岗"
        elif salary > 20000:
            return "高级技术岗"
        elif salary > 16000:
            return f"中高级{edu if is_high_edu else ''}技术岗".replace("本科技术岗", "技术岗")
        elif salary >= 12000 and exp < 2:
            return "入门分析岗"
        elif salary >= 8000 and exp < 1.5:
            return "初级入门岗"
        elif salary >= 8000:
            return "中级技术岗"
        else:
            return "初级通用岗"

    # ================================================================
    # 保存结果
    # ================================================================

    def _save_results(self):
        """保存聚类结果"""

        # 1. 簇画像JSON（给Flask用）
        profile_path = os.path.join(self.output_dir, "cluster_profile.json")
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        logger.info(f"📦 簇画像: {profile_path}")

        # 2. 标签追加到CSV（方便后续追溯每条记录属于哪个簇）
        if self.labels is not None and "cluster" in self.df.columns:
            label_path = os.path.join(config.CLEANED_DIR, "data_with_clusters.csv")
            self.df.to_csv(label_path, index=False, encoding="utf-8-sig")
            logger.info(f"📦 带簇标签的数据: {label_path}")

        # 3. 聚类可视化（用前2个SVD维度画散点图）
        self._plot_clusters()

    def _plot_clusters(self):
        """用前2个特征维度画聚类散点图"""
        if self.X_combined.shape[1] < 2:
            return

        # 用薪资和经验作为坐标轴（可解释性强）
        salary_idx = self.feature_names.index("salary_avg")
        exp_idx = self.feature_names.index("exp_avg")
        X_plot = self.X_combined[:, [salary_idx, exp_idx]]

        fig, ax = plt.subplots(figsize=(10, 7))
        colors = plt.cm.Set2(np.linspace(0, 1, self.optimal_k))

        for c in range(self.optimal_k):
            mask = self.labels == c
            cluster_name = self.results.get("cluster_names", {}).get(c, f"簇{c}")
            ax.scatter(
                X_plot[mask, 0], X_plot[mask, 1],
                c=[colors[c]], label=cluster_name,
                alpha=0.6, s=20, edgecolors="white", linewidth=0.3,
            )

        ax.set_title("IT岗位聚类结果（薪资 vs 经验）", fontsize=14, fontweight="bold")
        ax.set_xlabel("标准化薪资", fontsize=12)
        ax.set_ylabel("标准化经验", fontsize=12)
        ax.legend(loc="upper right", fontsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout()
        filepath = os.path.join(self.chart_dir, "cluster_scatter.png")
        plt.savefig(filepath, dpi=150, bbox_inches="tight")
        plt.close()
        logger.info(f"📈 聚类散点图: {filepath}")


if __name__ == "__main__":
    clusterer = JobClusterer()
    clusterer.run()
