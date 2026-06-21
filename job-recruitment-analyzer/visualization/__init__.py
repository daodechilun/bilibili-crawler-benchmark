"""
可视化模块 (visualization)
=========================
负责Flask后端 + ECharts前端仪表盘。

包含：
  - app.py            → Flask应用（2个路由：首页 + JSON API）
  - templates/index.html → 大屏页面（6图联动 + 筛选 + 暗色主题）
  - static/css/style.css → 暗色主题样式
  - static/china.json → 中国地图GeoJSON（需手动下载）
"""
from visualization.app import app

__all__ = ["app"]
