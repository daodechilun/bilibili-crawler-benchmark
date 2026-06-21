"""
分析模块 (analysis)
===================
负责描述性统计 + ML建模（薪资预测回归 + KMeans岗位聚类）。

包含：
  - statistics.py     → 描述性统计（6个维度 → JSON + PNG图表）
  - salary_predict.py → 薪资预测回归（3模型对比 + 特征重要性）
  - clustering.py     → KMeans岗位聚类（画像分析 + 业务命名）
"""
from analysis.statistics import StatisticsAnalyzer
from analysis.salary_predict import SalaryPredictor
from analysis.clustering import JobClusterer

__all__ = ["StatisticsAnalyzer", "SalaryPredictor", "JobClusterer"]
