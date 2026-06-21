# 实验八：Scrapy框架开发与分布式实战

## 项目结构

```
scrapy_demo/
├── scrapy.cfg                  # Scrapy 部署配置
├── requirements.txt            # Python 依赖
└── scrapy_demo/               # 项目包
    ├── __init__.py
    ├── items.py               # Item 数据模型
    ├── middlewares.py         # 下载中间件（随机UA）
    ├── pipelines.py           # 数据管道（JSON/JSONL/CSV）
    ├── settings.py            # 配置文件（含分布式配置）
    └── spiders/
        ├── __init__.py
        ├── demo.py            # 基础爬虫（单机）
        └── distributed_demo.py # 分布式爬虫（scrapy-redis）
```

## 环境配置

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 安装 Redis（Windows）
# 下载: https://github.com/tporadowski/redis/releases
# 启动: redis-server.exe

# 3. 验证 Scrapy
scrapy version
```

## 运行方式

### 单机基础爬虫
```bash
cd scrapy_demo
scrapy crawl demo
```

### 分布式爬虫（需先启动 Redis）
```bash
# 1. 启用 settings.py 中的分布式配置（取消注释）

# 2. 推送起始 URL 到 Redis
redis-cli lpush distributed_demo:start_urls "https://quotes.toscrape.com/"

# 3. 多终端启动爬虫
scrapy crawl distributed_demo
```

## 实验说明

本实验通过 Scrapy 框架基础开发与分布式部署实战，帮助学生建立工程化爬虫思维：

1. **任务一**：项目初始化与基础爬虫开发（demo.py）
2. **任务二**：ItemPipeline 数据持久化（pipelines.py）
3. **任务三**：随机 UA 下载中间件（middlewares.py）
4. **任务四**：scrapy-redis 分布式部署（distributed_demo.py）
5. **任务五**：对比分析与总结
