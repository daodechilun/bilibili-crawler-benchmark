"""
薪资预测回归模型
================
对比三种回归模型，选出最优用于薪资预测。

特征工程：
  city_tier     → LabelEncoder（一线=2, 新一线=1, 二线=0）
  education     → OrdinalEncoder（不限=0, 大专=1, 本科=2, 硕士=3, 博士=4）
  exp_avg       → 连续值（exp_min和exp_max的均值）
  skill_count   → 连续值（技能标签数量）
  is_face       → 布尔特征（是否面议）

目标变量：
  salary_avg 取对数 → np.log1p(salary_avg)
  🔥 薪资分布右偏（少数人极高），取对数使其接近正态，
     线性回归和树模型的效果都会大幅提升。

模型对比：
  1. 线性回归（基线，解释性最强）
  2. 随机森林（捕捉非线性，特征重要性）
  3. XGBoost（前沿算法，通常最优）

评估指标：R² + RMSE + MAE（三指标互验）
"""
import os
import json
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from loguru import logger

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder, OrdinalEncoder
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from xgboost import XGBRegressor

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config

plt.rcParams["font.sans-serif"] = ["SimHei", "PingFang SC", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

# ============================================================
# 学历有序编码
# ============================================================
EDUCATION_ORDER = {"不限": 0, "大专": 1, "本科": 2, "硕士": 3, "博士": 4}

CITY_TIER_ORDER = {"其他": 0, "二线": 0, "新一线": 1, "一线": 2}


class SalaryPredictor:
    """
    薪资预测器
    ----------
    流程：加载数据 → 特征工程 → 训练三模型 → 对比评估 → 输出结果

    用法：
        predictor = SalaryPredictor()
        predictor.run()
    """

    def __init__(self):
        self.cleaned_path = os.path.join(config.CLEANED_DIR, "cleaned_data.csv")
        self.output_dir = os.path.dirname(os.path.abspath(__file__))
        self.chart_dir = os.path.join(config.CHART_DIR)
        self.df = None
        self.X_train, self.X_test = None, None
        self.y_train, self.y_test = None, None
        self.models = {}
        self.results = {}

    def run(self):
        """一键运行薪资预测全流程"""
        logger.info("=" * 60)
        logger.info("💰 薪资预测建模启动")
        logger.info("=" * 60)

        self._load()
        self._feature_engineering()
        self._train_models()
        self._evaluate()
        self._feature_importance()
        self._save_results()

        logger.info("✅ 薪资预测建模完成")
        return self.results

    # ================================================================
    # 加载数据
    # ================================================================

    def _load(self):
        """加载清洗数据"""
        self.df = pd.read_csv(self.cleaned_path, encoding="utf-8-sig")
        for col in ["salary_avg", "salary_min", "salary_max", "exp_min", "exp_max"]:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors="coerce")
        logger.info(f"📂 加载数据: {len(self.df)} 条")

    # ================================================================
    # 特征工程
    # ================================================================

    def _feature_engineering(self):
        """构建特征矩阵 X 和目标向量 y"""
        logger.info("🔧 特征工程...")
        df = self.df.copy()

        # --- 目标变量：取对数（处理右偏） ---
        df["salary_log"] = np.log1p(df["salary_avg"].fillna(0))
        df = df[df["salary_avg"].notna() & (df["salary_avg"] > 0)]  # 删除无效薪资

        # --- 特征1: city_tier（标签编码） ---
        df["city_tier_enc"] = df["city_tier"].fillna("其他").map(CITY_TIER_ORDER)
        df["city_tier_enc"] = df["city_tier_enc"].fillna(0)

        # --- 特征2: education（有序编码） ---
        df["education_enc"] = df["education"].fillna("不限").map(EDUCATION_ORDER)
        df["education_enc"] = df["education_enc"].fillna(0)

        # --- 特征3: exp_avg（经验均值） ---
        df["exp_avg"] = df[["exp_min", "exp_max"]].mean(axis=1)
        df["exp_avg"] = df["exp_avg"].fillna(0)

        # --- 特征4: skill_count（技能数量） ---
        def count_skills(tags):
            if pd.isna(tags) or str(tags) == "nan" or not str(tags).strip():
                return 0
            return len([t.strip() for t in str(tags).split(",") if t.strip()])

        df["skill_count"] = df["skill_tags"].apply(count_skills)

        # --- 特征5: is_face（是否面议） ---
        df["is_face"] = df.get("salary_text", "").fillna("").str.contains("面议", na=False).astype(int)

        # --- 特征6: company_size（公司规模编码） ---
        size_map = {
            "少于50人": 1, "50-150人": 2, "150-500人": 3,
            "500-1000人": 4, "1000-5000人": 5, "5000-10000人": 6, "10000人以上": 7,
        }
        df["company_size_enc"] = df["company_size"].map(size_map).fillna(3)

        # --- 组装特征矩阵 ---
        feature_cols = [
            "city_tier_enc", "education_enc", "exp_avg",
            "skill_count", "is_face", "company_size_enc",
        ]
        X = df[feature_cols].fillna(0).values
        y = df["salary_log"].values

        logger.info(f"   特征维度: {X.shape[1]}（{feature_cols}）")
        logger.info(f"   有效样本: {len(y)} 条")
        logger.info(f"   薪资范围: {df['salary_avg'].min():.0f} ~ {df['salary_avg'].max():.0f} 元/月")
        logger.info(f"   薪资对数均值: {y.mean():.2f}, 标准差: {y.std():.2f}")

        # 划分训练/测试集
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        self.feature_names = feature_cols

    # ================================================================
    # 训练三个模型
    # ================================================================

    def _train_models(self):
        """训练线性回归、随机森林、XGBoost"""
        logger.info("🤖 训练模型...")

        # 模型1: 线性回归（基线）
        lr = LinearRegression()
        lr.fit(self.X_train, self.y_train)
        self.models["LinearRegression"] = lr
        logger.info("   ✅ 线性回归训练完成")

        # 模型2: 随机森林
        rf = RandomForestRegressor(**config.RF_PARAMS)
        rf.fit(self.X_train, self.y_train)
        self.models["RandomForest"] = rf
        logger.info("   ✅ 随机森林训练完成")

        # 模型3: XGBoost
        xgb_params = config.XGB_PARAMS.copy()
        xgb_params.pop("n_jobs", None)  # XGBoost新版不用n_jobs
        xgb = XGBRegressor(**xgb_params, verbosity=0)
        xgb.fit(self.X_train, self.y_train)
        self.models["XGBoost"] = xgb
        logger.info("   ✅ XGBoost训练完成")

    # ================================================================
    # 评估对比
    # ================================================================

    def _evaluate(self):
        """
        评估三个模型

        🔥 注意：评估时把对数预测值还原为原始薪资，
            这样计算出的RMSE和MAE才有实际意义（单位：元）。
        """
        logger.info("\n📊 模型评估:")

        eval_results = []
        for name, model in self.models.items():
            # 对数空间预测 → 还原为原始薪资
            y_pred_log = model.predict(self.X_test)
            y_pred = np.expm1(y_pred_log)  # 还原：exp(log(y)) - 1
            y_true = np.expm1(self.y_test)

            # 三个指标
            r2 = r2_score(y_true, y_pred)
            rmse = np.sqrt(mean_squared_error(y_true, y_pred))
            mae = mean_absolute_error(y_true, y_pred)

            # 交叉验证R²（5折）
            try:
                cv_scores = cross_val_score(model, self.X_train, self.y_train, cv=5, scoring="r2")
                cv_r2 = cv_scores.mean()
            except Exception:
                cv_r2 = None

            eval_results.append({
                "model": name,
                "R2": round(r2, 4),
                "RMSE": round(rmse, 0),
                "MAE": round(mae, 0),
                "CV_R2_mean": round(cv_r2, 4) if cv_r2 else None,
            })

            logger.info(f"   {name}: R²={r2:.4f}, RMSE={rmse:.0f}元, MAE={mae:.0f}元")

        # 找最优
        best = max(eval_results, key=lambda x: x["R2"])
        logger.info(f"\n🏆 最优模型: {best['model']} (R²={best['R2']:.4f})")

        self.results["model_compare"] = eval_results
        self.results["best_model"] = best["model"]

        # 保存对比表CSV
        compare_df = pd.DataFrame(eval_results)
        compare_path = os.path.join(self.output_dir, "model_compare.csv")
        compare_df.to_csv(compare_path, index=False, encoding="utf-8-sig")
        logger.info(f"   对比表: {compare_path}")

    # ================================================================
    # 特征重要性
    # ================================================================

    def _feature_importance(self):
        """
        提取随机森林和XGBoost的特征重要性
        """
        logger.info("\n[KEY] Feature importance analysis:")

        # 随机森林特征重要性
        rf = self.models.get("RandomForest")
        rf_importances = {}
        if rf and hasattr(rf, "feature_importances_"):
            rf_importances = {k: float(v) for k, v in
                             zip(self.feature_names, rf.feature_importances_)}
            for feat, imp in sorted(rf_importances.items(), key=lambda x: -x[1]):
                logger.info(f"     {feat}: {imp:.4f}")

        # XGBoost特征重要性
        xgb = self.models.get("XGBoost")
        xgb_importances = {}
        if xgb and hasattr(xgb, "feature_importances_"):
            xgb_importances = {k: float(v) for k, v in
                              zip(self.feature_names, xgb.feature_importances_)}
            for feat, imp in sorted(xgb_importances.items(), key=lambda x: -x[1]):
                logger.info(f"     {feat}: {imp:.4f}")

        self.results["feature_importance"] = {
            "random_forest": rf_importances,
            "xgboost": xgb_importances,
            "feature_names": self.feature_names,
        }

        # 保存JSON
        imp_path = os.path.join(self.output_dir, "feature_importance.json")
        with open(imp_path, "w", encoding="utf-8") as f:
            json.dump(self.results["feature_importance"], f, ensure_ascii=False, indent=2)

        # 画特征重要性图
        if rf_importances:
            self._plot_importance(rf_importances)

    def _plot_importance(self, importances: dict):
        """绘制特征重要性柱状图"""
        sorted_items = sorted(importances.items(), key=lambda x: x[1])
        labels = [item[0] for item in sorted_items]
        values = [item[1] for item in sorted_items]

        fig, ax = plt.subplots(figsize=(10, 5))
        colors = plt.cm.Reds(np.linspace(0.3, 0.9, len(labels)))
        ax.barh(labels, values, color=colors, edgecolor="white")
        ax.set_title("特征重要性排序（随机森林）", fontsize=14, fontweight="bold")
        ax.set_xlabel("重要性", fontsize=12)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout()
        filepath = os.path.join(self.chart_dir, "feature_importance.png")
        plt.savefig(filepath, dpi=150, bbox_inches="tight")
        plt.close()

    # ================================================================
    # 保存结果
    # ================================================================

    def _save_results(self):
        """保存所有结果为JSON（供Flask调用）"""
        filepath = os.path.join(self.output_dir, "salary_predict_results.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        logger.info(f"📦 预测结果: {filepath}")


if __name__ == "__main__":
    predictor = SalaryPredictor()
    predictor.run()
