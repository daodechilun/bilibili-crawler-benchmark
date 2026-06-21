# 网络爬虫工程实践

网络数据采集的工程化实践，覆盖从动态网页爬取、反爬对抗、Scrapy 框架开发到全栈数据分析系统的完整链路。包含三个独立子项目，难度与技术栈逐级递进。

## 项目概览

| 子项目 | 技术栈 | 亮点 |
|--------|--------|------|
| **IT 招聘数据分析系统**（大作业） | Stealth 爬虫 + MySQL + Scikit-learn + Flask | 全栈：采集→清洗→建模→可视化，~4000 行 |
| **Scrapy 分布式爬虫**（实验八） | Scrapy + Redis | 框架化、分布式调度 |
| **Ajax vs Selenium 方案对比**（实验七） | requests / selenium + 性能基准 | 100 倍效率差的量化对比 |

---

## 一、IT 岗位招聘数据分析系统（核心项目）

针对 51job 招聘平台，采集 4 个 IT 岗位方向（数据分析 / Python / AI 算法 / 大数据）在 10 个城市的招聘数据，完成清洗入库、统计建模、薪资预测与可视化大屏。

### 技术架构

```
采集(Stealth爬虫) → 清洗(规则+校验) → 存储(MySQL+CSV) → 分析(统计+ML) → 可视化(Flask)
```

### 模块设计（近 4000 行）

| 模块 | 行数 | 职责 |
|------|------|------|
| `crawler/` | ~700 | Stealth 浏览器绕 WAF、Cookie 管理、代理池、UA 池、指数退避重试 |
| `parser/` | ~460 | 职位字段解析、薪资区间解析（"15k-25k·14薪"→数值） |
| `cleaner/` | ~880 | 编码映射、城市分级、去重、字段校验 |
| `storage/` | ~370 | MySQL（PyMySQL）+ CSV 双写，schema.sql 建表 |
| `analysis/` | ~1240 | 描述统计 + 薪资回归（RF/XGBoost）+ KMeans 岗位聚类 |
| `visualization/` | Flask app | ECharts 大屏、中国地图薪资热力图 |

### 技术亮点

- **反爬对抗**：Stealth 浏览器方案隐藏 webdriver 特征、动态 Cookie 池、代理 IP 池、20 个 UA 轮换、随机延时 + 指数退避重试，成功绕过 51job 的 WAF 防护。
- **工程化配置**：全局 `config.py` 统一管理爬虫参数、反爬策略、DB 连接、ML 超参，改一处全项目生效。
- **机器学习建模**：薪资预测对比 Random Forest 与 XGBoost；TF-IDF 向量化技能关键词后做 KMeans 聚类，输出岗位画像。
- **一键编排**：`python main.py all` 串联采集→清洗→分析→可视化全流程。

### 运行

```bash
cd job-recruitment-analyzer
pip install -r requirements.txt
# 配置 MySQL 连接（修改 config.py 中的 DB_CONFIG）
python main.py crawl       # 1. 采集
python main.py clean       # 2. 清洗入库
python main.py analyze     # 3. 统计 + ML 建模
python main.py visualize   # 4. 启动 Flask 大屏 → http://127.0.0.1:5000
python main.py all         # 一键全流程
```

---

## 二、Scrapy 分布式爬虫（实验八）

用 Scrapy 框架重构爬虫，演示框架化的 Spider/Pipeline/Middleware 设计，以及基于 Redis 的分布式调度方案。

```
实验/实验八_Scrapy框架开发与分布式实战/
└── exp8_scrapy_demo/
    ├── scrapy.cfg
    ├── scrapy_demo/
    │   ├── items.py / middlewares.py / pipelines.py / settings.py
    │   └── spiders/        # demo.py（基础）+ distributed_demo.py（分布式）
    └── README.md
```

---

## 三、Ajax vs Selenium 方案对比（实验七）

针对 Bilibili 热门视频榜单，实现并**量化对比**两种动态网页采集方案的性能差异。

| 方案 | 技术栈 | 吞吐 | 资源占用 |
|------|--------|------|---------|
| Ajax 接口 | requests + JSON 解析 | **500 条 / 1.44s**（0.14s/页） | 内存 <100MB |
| Selenium | webdriver + ChromeDriver | 60 条 / 22s（2-4s/页） | 内存 300-800MB |

**结论**：在接口可抓包的场景下，Ajax 方案效率约为 Selenium 的 **100 倍**；Selenium 适用于接口加密或反爬严格的兜底场景。

核心实现：
- Ajax：抓包 B站 `popular` 接口，构造完整浏览器请求头（UA/Referer 防反爬），指数退避重试。
- Selenium：CDP 命令隐藏 webdriver 属性（反检测），显式等待 + 页面滚动触发懒加载。

---

## 运行环境

- Python 3.10
- MySQL 8.x（大作业存储）
- Node.js（可选，用于生成分析报告）
